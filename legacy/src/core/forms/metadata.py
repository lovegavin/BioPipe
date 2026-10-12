"""Axis-aware metadata operations. Inputs and their nested maps stay immutable."""
import numbers

import numpy as np

from src.core.errors import StepError


def project_metadata(form, selections=None, *, keep_dims=None, rename=None, derived=False):
    selections, rename = selections or {}, rename or {}
    kept = set(form.dims if keep_dims is None else keep_dims)
    info = dict(form.info)
    axis_info = {}
    for dim, fields in form.axis_info.items():
        if dim not in kept:
            for field in fields:
                info.pop(field, None)
            continue
        axis_info[rename.get(dim, dim)] = list(fields)
        if dim in selections:
            for field in fields:
                value = info[field]
                indices = selections[dim]
                info[field] = value[indices].copy() if isinstance(value, np.ndarray) else [value[int(i)] for i in indices]
    encoders = {}
    for dim, fields in info.get("encoders", {}).items():
        if dim not in kept:
            continue
        labels = set(form.labels.get(dim, {}))
        if dim in selections:
            positions = set(map(int, selections[dim]))
            labels = {label for label, pos in form.labels[dim].items() if pos in positions}
        if derived:
            labels = set()  # Original data columns no longer contain encoded values.
        fields = {key: encoder for key, encoder in fields.items()
                  if key in labels or key in form.axis_info.get(dim, [])}
        if fields:
            encoders[rename.get(dim, dim)] = fields
    if encoders:
        info["encoders"] = encoders
    else:
        info.pop("encoders", None)
    if derived:
        for key in ("representation", "ploidy", "alphabet"):
            info.pop(key, None)
    return info, axis_info


def equal_metadata(left, right):
    if left is right:
        return True
    if hasattr(left, "mapping") and hasattr(right, "mapping"):
        return type(left) is type(right) and equal_metadata(left.mapping, right.mapping)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equal_metadata(left[k], right[k]) for k in left)
    if isinstance(left, (list, tuple, np.ndarray)) and isinstance(right, (list, tuple, np.ndarray)):
        return len(left) == len(right) and all(equal_metadata(a, b) for a, b in zip(left, right))
    if isinstance(left, numbers.Real) and isinstance(right, numbers.Real) and np.isnan(left) and np.isnan(right):
        return True
    return bool(left == right)


def concat_metadata(forms, axis):
    """Union aligned annotations; refuse conflicting annotations/encodings."""
    ref = forms[0]
    if any(not equal_metadata(f.info.get("missing_code"), ref.info.get("missing_code")) for f in forms[1:]):
        raise StepError("concat: missing_code differs; normalize missing values before concatenation")
    bindings = {}
    for form in forms:
        for dim, fields in form.axis_info.items():
            for key in fields:
                if key in bindings and bindings[key] != dim:
                    raise StepError(f"concat: info.{key} is bound to different axes")
                if any(key in other.info and key not in other.axis_info.get(dim, []) for other in forms):
                    raise StepError(f"concat: info.{key} mixes scalar and axis annotations")
                bindings[key] = dim
    info = {key: value for key, value in ref.info.items()
            if key not in bindings and key != "encoders" and all(key in f.info and equal_metadata(value, f.info[key]) for f in forms[1:])}
    if not all(f.info.get("representation") == ref.info.get("representation") for f in forms):
        info.pop("representation", None)
        info.pop("ploidy", None)
    axis_info = {}
    for key, dim in bindings.items():
        if dim == axis:
            info[key] = [value for f in forms for value in f.info.get(key, [None] * f.data.shape[f.axis(dim)])]
        else:
            values = [f.info[key] for f in forms if key in f.info]
            if any(not equal_metadata(values[0], value) for value in values[1:]):
                raise StepError(f"concat: conflicting info.{key} on aligned axis {dim}")
            info[key] = values[0].copy() if isinstance(values[0], np.ndarray) else list(values[0])
        axis_info.setdefault(dim, []).append(key)
    encoders = {}
    for form in forms:
        for dim, fields in form.info.get("encoders", {}).items():
            for key, encoder in fields.items():
                existing = encoders.setdefault(dim, {}).get(key)
                if existing is not None and not equal_metadata(existing, encoder):
                    raise StepError(f"concat: incompatible encoders for {dim}.{key}")
                encoders[dim][key] = encoder
    if encoders:
        info["encoders"] = encoders
    return info, axis_info
