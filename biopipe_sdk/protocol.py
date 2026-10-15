"""JSON-compatible public descriptors and parameter validation."""
from copy import deepcopy
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = 1


class Descriptor(BaseModel):
    # Legacy UI fields are retained as extension fields in catalog v1.
    model_config = ConfigDict(extra="allow")
    protocol_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]{0,79}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    kind: Literal["operator", "reader"]
    entry_point: str
    title: str
    category: str | None = Field(default=None, description="Operator library category, independent of package origin. Custom labels are allowed.")
    icon: str | None = Field(default=None, description="Optional module-relative image path or Studio icon name. Missing or unknown names use the category default.")
    icon_image: str | None = Field(default=None, pattern=r"^data:image/(png|jpeg|webp|gif|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$", description="SDK-generated portable image data; authors declare a relative path in icon.")
    parameters_schema: dict[str, Any]
    contracts: dict[str, Any]
    resources: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list, description="PEP 508 dependencies; compatible versions share the host runtime, conflicting versions use a private dependency directory and subprocess with the same Python.")
    dependency_imports: list[str] = Field(default_factory=list, description="Optional import smoke checks, run outside the UI process.")

    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, value):
        from .dependencies import requirements
        return requirements(value)

    @field_validator('dependency_imports')
    @classmethod
    def validate_imports(cls, value):
        from .dependencies import imports
        return imports(value)


class PackageDescriptor(BaseModel):
    """One installation unit; operator identities remain independent of origin."""
    model_config = ConfigDict(extra="allow")
    protocol_version: Literal[1] = 1
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    version: str
    title: str | None = None
    origin: Literal["bundled", "wheel"] = "wheel"
    descriptors: list[Descriptor]


def validate_schema(schema):
    Draft202012Validator.check_schema(schema)
    if schema.get("type") != "object":
        raise ValueError("Parameter schema must describe an object")
    # Schemas are self-contained, so validation never fetches remote documents.
    def check(value):
        if isinstance(value, dict):
            for reference in ("$ref", "$dynamicRef"):
                if reference in value and not value[reference].startswith("#"):
                    raise ValueError("Only local JSON Schema references are supported")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(schema)


def validate_parameters(schema, params):
    validate_schema(schema)
    result = deepcopy(params)
    for name, field in schema.get("properties", {}).items():
        if name not in result and "default" in field:
            result[name] = deepcopy(field["default"])
    errors = sorted(Draft202012Validator(schema).iter_errors(result), key=lambda error: str(error.path))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str, e.path)) or 'params'}: {e.message}" for e in errors))
    return result


def schema_to_fields(schema):
    result = []
    for key, value in schema.get("properties", {}).items():
        kind = value.get("type", "object")
        if isinstance(kind, list):
            concrete = [item for item in kind if item != "null"]
            kind = value.get("x-ui-type", concrete[0] if len(concrete) == 1 else "object")
        field = {"key": key, "label": value.get("title", key),
                 "type": "choice" if "enum" in value else {"array": "json", "object": "json"}.get(kind, kind),
                 "required": key in schema.get("required", [])}
        if value.get("description"):
            field["description"] = value["description"]
        if value.get("type") == "array" and value.get("items", {}).get("type") == "string":
            field["type"] = "list"
        if not isinstance(field["type"], str):
            field["type"] = "json"
        for source, target in (("default", "default"), ("minimum", "min"), ("maximum", "max"), ("enum", "options")):
            if source in value:
                field[target] = deepcopy(value[source])
        result.append(field)
    return result


def legacy_schema(fields, defaults):
    properties = {}
    for field in fields:
        kind = field["type"]
        value = {"title": field.get("label", field["key"])}
        types = {"list": "array", "scalar": ["string", "number"], "json": ["object", "array"]}
        if kind == "choice":
            value["enum"] = field.get("options", [])
        else:
            value["type"] = types.get(kind, kind)
        for source, target in (("min", "minimum"), ("max", "maximum")):
            if source in field:
                value[target] = field[source]
        if field["key"] in defaults:
            value["default"] = defaults[field["key"]]
        properties[field["key"]] = value
    # Existing manifests can contain additional engine parameters. The adapter
    # advertises them without tightening historical validation behavior.
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "properties": properties, "additionalProperties": True,
            "required": [f["key"] for f in fields if f.get("required") and f["key"] not in defaults]}


def describe_operator(cls, legacy=None):
    packaged = getattr(cls, "_package_descriptor", None)
    value = deepcopy(packaged or legacy or {})
    schema = getattr(cls, "parameters_schema", None)
    if schema is not None:
        validate_schema(schema)
        if not packaged:
            value["parameters"] = schema_to_fields(schema)
            value["runtime_defaults"] = {key: field["default"] for key, field in schema.get("properties", {}).items() if "default" in field}
    else:
        schema = legacy_schema(value.get("parameters", []), value.get("runtime_defaults", {}))
    output_parameter = getattr(cls, "output_parameter", None)
    value.update(protocol_version=1, id=cls.name, version=getattr(cls, "version", "1.0.0"), kind="operator",
                 entry_point=f"{cls.__module__}:{cls.__name__}", module=cls.__module__,
                 title=getattr(cls, "title", None) or value.get("title", cls.name),
                 parameters_schema=schema, name=cls.name, inputs_arity=cls.inputs_arity,
                 outputs=list(cls.outputs), output_parameter=output_parameter,
                 legacy_parameters=bool(getattr(cls, "legacy_parameters", False)),
                 contracts={"version": 1, "inputs": cls.input_contracts, "output": cls.output_contract},
                 resources={"memory_modes": ["full", "stream"] if cls.supports_streaming else ["full"],
                            "supports_cuda": bool(getattr(cls, "supports_cuda", False)),
                            "estimate": "estimate_memory",
                            **({"stream_protocol": cls.stream_protocol,
                                "stream_buffer_multiplier": cls.stream_buffer_multiplier,
                                "stream_fixed_bytes": cls.stream_fixed_bytes} if cls.supports_streaming else {})})
    # Declarations travel through source scans and wheel manifests alike. A base
    # class's None defaults must not erase older packaged presentation metadata.
    for field in ("category", "icon"):
        declared = getattr(cls, field, None)
        if declared is not None:
            value[field] = declared
    if value.get("category") is None:
        value["category"] = "Plugins"
    from biopipe_sdk.icons import resolve_icon
    resolve_icon(cls, value)
    from biopipe_sdk.dependencies import declarations
    value.update(declarations(cls, value))
    value.setdefault("description", (cls.__doc__ or "").strip())
    value.setdefault("input_type", "Form")
    value.setdefault("output_type", "Form" if cls.outputs or output_parameter else "Report")
    value.update(memory_modes=value["resources"]["memory_modes"], supports_cuda=value["resources"]["supports_cuda"])
    # Preserve the shape of previously built wheel manifests: optional display
    # fields that were never declared must not suddenly appear as null.
    return Descriptor.model_validate(value).model_dump(exclude_unset=True)


def describe_reader(reader):
    cls = type(reader)
    from biopipe_sdk.dependencies import declarations
    schema = getattr(cls, "parameters_schema", None) or {"type": "object", "additionalProperties": True}
    validate_schema(schema)
    return Descriptor(protocol_version=1, id=getattr(cls, "name", None) or cls.__name__,
                      version=getattr(cls, "version", "1.0.0"), kind="reader",
                      entry_point=f"{cls.__module__}:{cls.__name__}", title=getattr(cls, "title", None) or cls.__name__,
                      parameters_schema=schema, contracts={"version": 1, "inputs": [], "output": reader.output_contract},
                      parameters=schema_to_fields(schema),
                      resources={"memory_modes": ["full", "disk"] if reader.supports_disk_read else ["full"], "supports_cuda": False,
                                 **({"disk_protocol": reader.disk_protocol} if reader.supports_disk_read else {})},
                      name=cls.__name__, module=cls.__module__, extensions=list(reader.extensions),
                      requires_siblings=list(reader.requires_siblings), excludes_siblings=list(reader.excludes_siblings),
                      handles_compression=reader.handles_compression,
                      **({"file_input": deepcopy(reader.file_input)} if reader.file_input is not None else {}),
                      output_contract=reader.output_contract, **declarations(cls, getattr(cls, '_package_descriptor', None))).model_dump(exclude_unset=True)


def validate_output_rule(rule):
    modes = {"unknown", "declare", "project", "choose", "passthrough", "transform", "subset", "select", "drop", "rename", "transpose", "concat", "attach", "report", "none", "pca", "regress", "correction", "compare_groups", "cox_regression", "logrank_test"}
    if not isinstance(rule, dict) or rule.get("mode") not in modes:
        raise ValueError("Use a documented output contract mode")
    if rule["mode"] == "choose":
        if not isinstance(rule.get("param"), str) or not rule.get("cases"):
            raise ValueError("choose requires a parameter and non-empty cases")
        for case in rule["cases"].values():
            validate_output_rule(case)
        if "otherwise" in rule:
            validate_output_rule(rule["otherwise"])
    if rule["mode"] == "project":
        for axis in rule.get("prepend_dims", []) + rule.get("append_dims", []):
            if not isinstance(axis, dict) or not ("name" in axis or "input_axis" in axis):
                raise ValueError("Added dimensions require name or input_axis")
            ref = axis.get("input_axis")
            if ref is not None and (not isinstance(ref, list) or len(ref) != 2 or any(type(n) is not int or n < 0 for n in ref)):
                raise ValueError("input_axis must be [input_index, axis_index]")


def validate_port_rule(rule):
    if not isinstance(rule, dict):
        raise ValueError("Port contracts must be objects")
    if "numeric" in rule and not isinstance(rule["numeric"], bool):
        raise ValueError("Port numeric must be boolean")
    if rule.get("ndim") is not None and (type(rule["ndim"]) is not int or rule["ndim"] < 0):
        raise ValueError("Port ndim must be a nonnegative integer")
    if not isinstance(rule.get("info", {}), dict):
        raise ValueError("Port info must be an object")
    for key in ("dims", "labels", "parallel", "labels_any", "labels_axis"):
        value = rule.get(key, [])
        if not isinstance(value, list) and not (isinstance(value, dict) and isinstance(value.get("param"), str)):
            raise ValueError(f"Port {key} must be a list or parameter reference")


def validate_extension(cls, kind):
    """Strict authoring requirements for new extensions; legacy adapters stay permissive."""
    from src.task.step.base import Step
    from src.reader.base import Reader
    base = Step if kind == "operator" else Reader
    if not isinstance(cls, type) or not issubclass(cls, base):
        raise ValueError(f"Plugin entry must subclass {base.__name__}")
    if cls.parameters_schema is None:
        raise ValueError("Plugins must declare parameters_schema, including readers with no options")
    validate_schema(cls.parameters_schema)
    if not cls.output_contract:
        raise ValueError("Plugins must declare output_contract")
    if kind == "operator":
        if cls.output_parameter not in (None, "output"):
            raise ValueError("Plugin v1 supports only the dynamic output parameter 'output'")
        arity = cls.inputs_arity
        if arity != "*" and (type(arity) is not int or arity < 0 or arity > 20):
            raise ValueError("inputs_arity must be an integer from 0 to 20 or '*'")
        if cls.input_contracts is None or len(cls.input_contracts) != (1 if arity == "*" else arity):
            raise ValueError("Declare one input contract per port (one repeat contract for '*')")
        for contract in cls.input_contracts:
            validate_port_rule(contract)
        validate_output_rule(cls.output_contract)
        if cls.output_contract["mode"] not in {"report", "none", "unknown"} and not (cls.outputs or cls.output_parameter):
            raise ValueError("Form-producing operators must declare outputs or output_parameter")
        if cls.supports_streaming:
            if (cls.stream_protocol != "flat-reduction-v1" or cls.inputs_arity != 1
                    or cls.output_contract.get("mode") not in {"report", "none"}
                    or cls.outputs or cls.output_parameter or cls.run_stream is Step.run_stream):
                raise ValueError("Streaming requires flat-reduction-v1, one input, report-only output and run_stream")
            if (type(cls.stream_buffer_multiplier) is not int or cls.stream_buffer_multiplier < 1
                    or type(cls.stream_fixed_bytes) is not int or cls.stream_fixed_bytes < 0):
                raise ValueError("Stream buffer multiplier and fixed workspace must be valid integer estimates")
    else:
        validate_port_rule(cls.output_contract)
        if cls.supports_disk_read:
            if (cls.disk_protocol != "dense-writer-v1" or cls.probe is Reader.probe
                    or cls.read_to_disk is Reader.read_to_disk):
                raise ValueError("Disk readers require dense-writer-v1, probe and read_to_disk")
        if not cls.extensions or any(not isinstance(ext, str) or not ext.startswith(".") for ext in cls.extensions):
            raise ValueError("Readers must declare file extensions such as '.npy'")
