"""One startup catalog shared by the runtime and the local web studio."""
import ast
import inspect
import json
import textwrap
from pathlib import Path

from .memory.planner import FORM_STEPS
from .operator_categories import category_for_operator
from src.core.contracts import VERSION


def _preview_description(descriptor):
    """Every operator must have a one-line functional preview.

    Older bulk-generated operators have an empty docstring.  The fallback
    states the executable contract rather than inventing biological meaning.
    """
    text = (descriptor.get("description") or "").strip()
    if text:
        return text
    title = descriptor.get("title") or descriptor.get("name") or "Operator"
    arity = descriptor.get("inputs_arity")
    if arity == 0:
        lead = "无需数据输入"
    elif isinstance(arity, int):
        lead = f"接收 {arity} 个输入"
    else:
        lead = "接收可变数量的输入"
    output = descriptor.get("output_type") or "Form"
    properties = (descriptor.get("parameters_schema") or {}).get("properties") or {}
    params = [field.get("title") or key for key, field in properties.items()
              if key != "output"]
    detail = f"；主要参数：{'、'.join(params[:6])}" if params else ""
    return f"{title}：{lead}，输出 {output}{detail}。"


def build_catalog(registry, *, normalize_categories=True):
    definitions = json.loads(Path(__file__).with_name("operator_ui.json").read_text(encoding="utf-8"))
    operators = []
    for name, cls in sorted(registry.items()):
        descriptor = {
            "name": name, "module": cls.__module__, "inputs_arity": cls.inputs_arity,
            "outputs": list(cls.outputs),
            "output_parameter": getattr(cls, "output_parameter", None) or ("output" if name in FORM_STEPS else None),
            "memory_modes": ["full", "stream"] if getattr(cls, "supports_streaming", False) else ["full"],
            "supports_cuda": bool(getattr(cls, "supports_cuda", False)),
            "title": name, "category": "扩展算子", "input_type": "Form",
            "output_type": "Form" if cls.outputs or getattr(cls, "output_parameter", None) or name in FORM_STEPS else "Report",
            "description": (cls.__doc__ or "").strip().split("\n")[0], "parameters": [],
        }
        descriptor.update(definitions.get(name, {}))
        # Contracts are executable declarations, never overridden by UI copy.
        descriptor["contracts"] = {"version": VERSION, "inputs": cls.input_contracts,
                                   "output": cls.output_contract}
        # Preserve the operator's own defaults when importing existing YAML.
        # UI defaults are suggestions for newly added blocks, not migrations.
        defaults = {}
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
            for call in ast.walk(tree):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "get" and isinstance(call.func.value, ast.Attribute)
                        and call.func.value.attr == "step_params" and len(call.args) >= 2
                        and isinstance(call.args[0], ast.Constant)):
                    try:
                        defaults[call.args[0].value] = ast.literal_eval(call.args[1])
                    except (ValueError, TypeError):
                        pass
        except (OSError, TypeError, SyntaxError):
            pass
        descriptor["runtime_defaults"] = defaults
        from biopipe_sdk.protocol import describe_operator
        operator = describe_operator(cls, descriptor)
        if normalize_categories:
            operator["category"] = category_for_operator(name, operator.get("category"))
        operator["description"] = _preview_description(operator)
        operators.append(operator)
    from src.reader import READERS
    from biopipe_sdk.protocol import describe_reader
    readers = [describe_reader(reader) for reader in READERS]
    return {"schema_version": 1, "protocol_version": 1, "contract_version": VERSION, "operators": operators, "readers": readers}
