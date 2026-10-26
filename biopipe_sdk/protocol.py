"""JSON-compatible public descriptors and parameter validation."""
from copy import deepcopy
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = 2


class Descriptor(BaseModel):
    """Canonical, versioned extension declaration; UI projections are separate."""
    model_config = ConfigDict(extra="forbid")
    protocol_version: Literal[2] = 2
    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]{0,79}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    kind: Literal["operator", "reader"]
    entry_point: str
    title: str
    description: str = ""
    category: str | None = Field(default=None, description="Operator library category, independent of package origin. Custom labels are allowed.")
    icon: str | None = Field(default=None, description="Optional module-relative image path or Studio icon name. Missing or unknown names use the category default.")
    icon_image: str | None = Field(default=None, pattern=r"^data:image/(png|jpeg|webp|gif|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$", description="SDK-generated portable image data; authors declare a relative path in icon.")
    parameters_schema: dict[str, Any]
    contracts: dict[str, Any]
    resources: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list, description="PEP 508 dependencies; compatible versions share the host runtime, conflicting versions use a private dependency directory and subprocess with the same Python.")
    dependency_imports: list[str] = Field(default_factory=list, description="Optional import smoke checks, run outside the UI process.")
    inputs_arity: int | Literal["*"] = 0
    outputs: list[str] = Field(default_factory=list)
    output_parameter: Literal["output"] | None = None
    extensions: list[str] = Field(default_factory=list)
    requires_siblings: list[str] = Field(default_factory=list)
    excludes_siblings: list[str] = Field(default_factory=list)
    handles_compression: bool = False
    file_input: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    title_aliases: list[str] = Field(default_factory=list)
    title_parameter: dict[str, Any] | None = None

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
    model_config = ConfigDict(extra="forbid")
    protocol_version: Literal[2] = 2
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    version: str
    title: str | None = None
    origin: Literal["bundled", "wheel"] = "wheel"
    descriptors: list[Descriptor]
    dependencies: list[str] = Field(default_factory=list)


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
        if "x-ui-default" in value:
            field["default"] = deepcopy(value["x-ui-default"])
        if "x-ui-step" in value:
            field["step"] = value["x-ui-step"]
        result.append(field)
    return result


def _schema(cls):
    schema = deepcopy(cls.parameters_schema)
    if schema is None:
        raise ValueError(f"{cls.__name__}: protocol v2 requires parameters_schema; run the migration tool for v1 sources")
    for key, value in getattr(cls, "ui_defaults", {}).items():
        if key not in schema.get("properties", {}):
            raise ValueError(f"Unknown UI preset parameter: {key}")
        schema["properties"][key]["x-ui-default"] = deepcopy(value)
    validate_schema(schema)
    return schema


def describe_operator(cls):
    """Generate the sole executable declaration from the implementation class."""
    value = dict(protocol_version=PROTOCOL_VERSION, id=cls.name,
                 version=cls.version, kind="operator",
                 entry_point=f"{cls.__module__}:{cls.__name__}",
                 title=getattr(cls, "title", None) or cls.name,
                 description=getattr(cls, "description", None) or (cls.__doc__ or "").strip(),
                 parameters_schema=_schema(cls), inputs_arity=cls.inputs_arity,
                 outputs=list(cls.outputs), output_parameter=cls.output_parameter,
                 contracts={"version": 1, "inputs": cls.input_contracts, "output": cls.output_contract},
                 resources={"memory_modes": ["full", "stream"] if cls.supports_streaming else ["full"],
                            "supports_cuda": bool(getattr(cls, "supports_cuda", False)),
                            "estimate": "estimate_memory",
                            **({"stream_protocol": cls.stream_protocol,
                                "stream_buffer_multiplier": cls.stream_buffer_multiplier,
                                "stream_fixed_bytes": cls.stream_fixed_bytes} if cls.supports_streaming else {})})
    for key in ("category", "icon", "preview", "title_aliases", "title_parameter"):
        declared = getattr(cls, key, None)
        if declared is not None:
            value[key] = deepcopy(declared)
    value.setdefault("category", "Plugins")
    from biopipe_sdk.icons import resolve_icon
    from biopipe_sdk.dependencies import declarations
    resolve_icon(cls, value)
    value.update(declarations(cls))
    return Descriptor.model_validate(value).model_dump(exclude_unset=True)


def describe_reader(reader):
    cls = type(reader)
    from biopipe_sdk.dependencies import declarations
    value = dict(protocol_version=PROTOCOL_VERSION, id=getattr(cls, "name", None) or cls.__name__,
                 version=cls.version, kind="reader", entry_point=f"{cls.__module__}:{cls.__name__}",
                 title=getattr(cls, "title", None) or cls.__name__,
                 parameters_schema=_schema(cls), contracts={"version": 1, "inputs": [], "output": reader.output_contract},
                 resources={"memory_modes": ["full", "disk"] if reader.supports_disk_read else ["full"], "supports_cuda": False,
                            **({"disk_protocol": reader.disk_protocol} if reader.supports_disk_read else {})},
                 extensions=list(reader.extensions), requires_siblings=list(reader.requires_siblings),
                 excludes_siblings=list(reader.excludes_siblings), handles_compression=reader.handles_compression,
                 **({"file_input": deepcopy(reader.file_input)} if reader.file_input is not None else {}),
                 **declarations(cls))
    return Descriptor.model_validate(value).model_dump(exclude_unset=True)


def catalog_entry(descriptor):
    """UI projection. These derived fields are never stored in a package."""
    value = deepcopy(descriptor)
    schema = value["parameters_schema"]
    value["parameters"] = schema_to_fields(schema)
    value["runtime_defaults"] = {key: deepcopy(field["default"])
                                 for key, field in schema.get("properties", {}).items() if "default" in field}
    return value


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
    """One authoring contract for bundled and external implementations."""
    from src.task.step.base import Step
    from src.reader.base import Reader
    base = Step if kind == "operator" else Reader
    if not isinstance(cls, type) or not issubclass(cls, base):
        raise ValueError(f"Plugin entry must subclass {base.__name__}")
    if cls.parameters_schema is None:
        raise ValueError("Plugins must declare parameters_schema, including readers with no options")
    validate_schema(cls.parameters_schema)
    if hasattr(cls, "legacy_parameters"):
        raise ValueError("legacy_parameters was removed in protocol v2; migrate the source declaration")
    if not cls.output_contract:
        raise ValueError("Plugins must declare output_contract")
    if kind == "operator":
        if cls.output_parameter not in (None, "output"):
            raise ValueError("Protocol v2 supports only the dynamic output parameter 'output'")
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
