"""JSON-compatible public descriptors and parameter validation."""
from copy import deepcopy
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field

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
    parameters_schema: dict[str, Any]
    contracts: dict[str, Any]
    resources: dict[str, Any]


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
            kind = "object"  # Union values use the lossless JSON editor.
        field = {"key": key, "label": value.get("title", key),
                 "type": "choice" if "enum" in value else {"array": "json", "object": "json"}.get(kind, kind),
                 "required": key in schema.get("required", [])}
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
    value = deepcopy(legacy or {})
    schema = getattr(cls, "parameters_schema", None)
    if schema is not None:
        validate_schema(schema)
        value["parameters"] = schema_to_fields(schema)
        value["runtime_defaults"] = {key: field["default"] for key, field in schema.get("properties", {}).items() if "default" in field}
    else:
        schema = legacy_schema(value.get("parameters", []), value.get("runtime_defaults", {}))
    output_parameter = getattr(cls, "output_parameter", None)
    value.update(protocol_version=1, id=cls.name, version=getattr(cls, "version", "1.0.0"), kind="operator",
                 entry_point=f"{cls.__module__}:{cls.__name__}",
                 title=getattr(cls, "title", None) or value.get("title", cls.name),
                 parameters_schema=schema, name=cls.name, inputs_arity=cls.inputs_arity,
                 outputs=list(cls.outputs), output_parameter=output_parameter,
                 contracts={"version": 1, "inputs": cls.input_contracts, "output": cls.output_contract},
                 resources={"memory_modes": ["full", "stream"] if cls.supports_streaming else ["full"],
                            "supports_cuda": bool(getattr(cls, "supports_cuda", False)),
                            "estimate": "estimate_memory"})
    value.setdefault("category", getattr(cls, "category", "Plugins"))
    value.setdefault("description", (cls.__doc__ or "").strip())
    value.setdefault("input_type", "Form")
    value.setdefault("output_type", "Form" if cls.outputs or output_parameter else "Report")
    value.update(memory_modes=value["resources"]["memory_modes"], supports_cuda=value["resources"]["supports_cuda"])
    return Descriptor.model_validate(value).model_dump()


def describe_reader(reader):
    cls = type(reader)
    schema = getattr(cls, "parameters_schema", None) or {"type": "object", "additionalProperties": True}
    validate_schema(schema)
    return Descriptor(protocol_version=1, id=getattr(cls, "name", None) or cls.__name__,
                      version=getattr(cls, "version", "1.0.0"), kind="reader",
                      entry_point=f"{cls.__module__}:{cls.__name__}", title=getattr(cls, "title", None) or cls.__name__,
                      parameters_schema=schema, contracts={"version": 1, "inputs": [], "output": reader.output_contract},
                      resources={"memory_modes": ["full"], "supports_cuda": False},
                      name=cls.__name__, module=cls.__module__, extensions=list(reader.extensions),
                      requires_siblings=list(reader.requires_siblings), excludes_siblings=list(reader.excludes_siblings),
                      handles_compression=reader.handles_compression, output_contract=reader.output_contract).model_dump()


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
        modes = {"unknown", "declare", "project", "passthrough", "transform", "subset", "select", "drop", "rename", "transpose", "concat", "attach", "report", "none"}
        if cls.output_contract.get("mode") not in modes:
            raise ValueError("Use a documented generic output contract mode")
        if cls.supports_streaming:
            raise ValueError("Plugin v1 uses full mode; no generic chunk protocol is available yet")
    else:
        if not cls.extensions or any(not isinstance(ext, str) or not ext.startswith(".") for ext in cls.extensions):
            raise ValueError("Readers must declare file extensions such as '.npy'")
