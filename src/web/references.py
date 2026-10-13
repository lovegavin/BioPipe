"""Rewrite semantic data references when graph IDs/output aliases change."""
from copy import deepcopy


def remap_params(operator, params, names):
    result = deepcopy(params)
    if operator == "concat" and isinstance(result.get("align"), dict):
        keys = result["align"].get("key")
        if isinstance(keys, dict):
            result["align"]["key"] = {names.get(name, name): value for name, value in keys.items()}
    return result
