"""Versioned, JSON-serializable port contracts and conservative type inference.

Declarations live on Reader/Step classes. This module is deliberately independent
of discovery, the web API and the executor. An unknown fact never proves a type.
"""
from copy import deepcopy
import math
import numbers

import numpy as np

from src.core.errors import StepError

VERSION = 1
MISSING = {"type": ["number", "null"]}


def param(name, default=None):
    return {"param": name, "default": default}


def port(*, info=None, dims=None, labels=None, parallel=None, ndim=None, values=None):
    result = {"version": VERSION, "numeric": True, "info": info or {},
              "dims": dims or [], "labels": labels or [], "parallel": parallel or []}
    if ndim is not None:
        result["ndim"] = ndim
    if values:
        result["values"] = values
    return result


def reader_contract(*, representation=None, ploidy=None, coordinates=False, ndim=2, extra=None):
    info = {"missing_code": MISSING, "encoders": {"type": "object", "optional": True}, **(extra or {})}
    if representation:
        info["representation"] = {"type": "string", "const": representation}
        info["ploidy"] = {"type": "integer", "min": 1, **({"const": ploidy} if ploidy else {})}
    if coordinates:
        info.update(chrom={"type": "array", "items": "string"}, pos={"type": "array", "items": "integer"})
    return {**port(info=info, ndim=ndim, values="allele_count" if representation else None),
            "axis_fields": [{"axis": 0, "fields": ["chrom", "pos"]}] if coordinates else [],
            "info_open": False}


def resolve(value, params):
    if isinstance(value, dict):
        if "param" in value:
            return params.get(value["param"], resolve(value.get("default"), params))
        return {key: resolve(item, params) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, params) for item in value]
    return value


def unknown():
    return {"version": VERSION, "dims": None, "labels": {}, "info": {},
            "axis_info": {}, "info_open": True, "axis_info_open": True}


def _type(value):
    if value is None:
        return "null"
    if isinstance(value, (bool, np.bool_)):
        return "boolean"
    if isinstance(value, numbers.Integral):
        return "integer"
    if isinstance(value, numbers.Real):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple, np.ndarray)):
        return "array"
    return "object"


def describe_metadata(metadata, shape, numeric=True):
    info = {}
    for key, value in metadata.get("info", {}).items():
        rule = {"type": _type(value)}
        if rule["type"] in ("string", "integer", "number", "boolean", "null"):
            if isinstance(value, numbers.Real) and not math.isfinite(value):
                rule["display"] = str(value)
            else:
                rule["const"] = value.item() if isinstance(value, np.generic) else value
        info[key] = rule
    return {"version": VERSION, "ndim": len(shape), "numeric": numeric,
            "dims": list(metadata["dims"]),
            "labels": {dim: list(mapping) for dim, mapping in metadata["labels"].items()},
            "info": info, "axis_info": deepcopy(metadata.get("axis_info", {})),
            "info_open": False, "axis_info_open": False}


def describe_form(form):
    return describe_metadata(vars(form), form.data.shape, form.data.dtype.kind in "biuf")


def source_schema(contract, dims):
    if not contract:
        return {**unknown(), "dims": list(dims), "ndim": len(dims)}
    return {"version": VERSION, "ndim": contract.get("ndim", len(dims)), "numeric": True,
            "dims": list(dims), "labels": {dim: None for dim in dims},
            "info": deepcopy(contract.get("info", {})),
            "info_open": contract.get("info_open", True), "axis_info_open": False,
            "axis_info": {dims[rule["axis"]]: rule["fields"] for rule in contract.get("axis_fields", [])
                          if rule["axis"] < len(dims)}}


def compatible(schema, requirement):
    """Compare guarantees with requirements: compatible / incompatible / unknown."""
    errors, pending = [], []
    def check(ok, message):
        if ok is False:
            errors.append(message)
        elif ok is None:
            pending.append(message)
    if requirement is None:
        return {"status": "unknown", "reasons": ["算子尚未声明输入契约"]}
    if "ndim" in requirement:
        check(None if "ndim" not in schema else schema["ndim"] == requirement["ndim"],
              f"需要 {requirement['ndim']} 维数据")
    if requirement.get("numeric"):
        check(schema.get("numeric"), "需要数值张量")
    dims = schema.get("dims")
    for dim in requirement.get("dims", []):
        check(None if dim is None or dims is None else dim in dims, f"需要维度 {dim or '（待设置）'}")
    for key, rule in requirement.get("info", {}).items():
        actual = schema.get("info", {}).get(key)
        if actual is None:
            if not rule.get("optional"):
                check(None if schema.get("info_open", True) else False, f"缺少 info.{key}")
            continue
        if actual.get("optional") and not rule.get("optional"):
            check(None, f"info.{key} 读取后确认")
        expected_types = rule.get("type", [])
        expected_types = expected_types if isinstance(expected_types, list) else [expected_types]
        actual_types = actual.get("type", [])
        actual_types = actual_types if isinstance(actual_types, list) else [actual_types]
        if expected_types:
            allowed = set(expected_types) | ({"integer"} if "number" in expected_types else set())
            check(True if actual_types and set(actual_types) <= allowed else
                  False if actual_types and not set(actual_types) & allowed else None,
                  f"info.{key} 需要 {' / '.join(expected_types)}")
        expected = rule.get("enum", [rule["const"]] if "const" in rule else None)
        if expected is not None:
            options = actual.get("enum", [actual["const"]] if "const" in actual else None)
            check(None if options is None else True if all(v in expected for v in options)
                  else False if not any(v in expected for v in options) else None,
                  f"info.{key} 需要 {' / '.join(map(str, expected))}；上游为 {options if options is not None else '待读取'}")
        if "min" in rule:
            check(actual["const"] >= rule["min"] if isinstance(actual.get("const"), numbers.Real)
                  else True if actual.get("min", -math.inf) >= rule["min"] else None,
                  f"info.{key} 需要 ≥ {rule['min']}")
    for rule in requirement.get("labels", []):
        dim, values = rule.get("dim"), rule.get("values")
        if rule.get("optional") and values is None:
            continue
        values = values if isinstance(values, list) else [values]
        known = schema.get("labels", {}).get(dim)
        for field in values:
            check(None if field is None or known is None else field in known,
                  f"labels.{dim} 需要 {field or '（待设置）'}")
    for field in requirement.get("labels_any", []):
        candidates = list(schema.get("labels", {}).values())
        check(True if any(field in labels for labels in candidates if labels is not None) else
              None if field is None or not candidates or any(labels is None for labels in candidates) else False,
              f"需要字段 {field or '（待设置）'}")
    for rule in requirement.get("labels_axis", []):
        axis = rule["axis"]
        dim = dims[axis] if dims and axis < len(dims) else None
        known = schema.get("labels", {}).get(dim)
        values = rule.get("values", [])
        for field in values if isinstance(values, list) else [values]:
            check(None if field is None or known is None else field in known,
                  f"第 {axis + 1} 维需要字段 {field or '（待设置）'}")
    for rule in requirement.get("parallel", []):
        fields = rule.get("fields", [])
        fields = fields if isinstance(fields, list) else [fields]
        for field in fields:
            dim = rule.get("dim")
            axis_match = any(field in keys for d, keys in schema.get("axis_info", {}).items()
                             if dim is None or d == dim)
            labels = schema.get("labels", {}).get(dim)
            label_match = rule.get("allow_label") and labels is not None and field in labels
            uncertain = field is None or schema.get("axis_info_open", True) or (rule.get("allow_label") and labels is None)
            check(True if axis_match or label_match else None if uncertain else False,
                  f"需要 {field or '（待设置）'} 的轴注释" + (f"（{dim}）" if dim else ""))
    return {"status": "incompatible" if errors else "unknown" if pending else "compatible",
            "reasons": errors or pending}


def validate_form(form, requirement, where):
    form.validate()
    result = compatible(describe_form(form), requirement)
    if result["status"] != "compatible":
        # An undeclared extension still gets Form's structural validation.
        if requirement is None:
            return
        raise StepError(f"{where} contract: " + "; ".join(result["reasons"]))
    for key, rule in (requirement or {}).get("info", {}).items():
        if key in form.info and rule.get("items"):
            types = rule["items"] if isinstance(rule["items"], list) else [rule["items"]]
            if any(_type(value) not in types and not (_type(value) == "integer" and "number" in types)
                   for value in form.info[key]):
                raise StepError(f"{where} contract: info.{key} requires {rule['items']} items")
    validate_values(form.data, form.info, requirement, where, form=form)


def validate_values(data, info, requirement, where, *, form=None):
    """Data checks use bounded buffers, including non-contiguous tensors."""
    check = (requirement or {}).get("values")
    if check == "pvalue" and form is not None:
        rule = requirement["labels"][0]
        data = np.take(data, form.labels[rule["dim"]][rule["values"]], axis=form.axis(rule["dim"]))
    if check not in ("allele_count", "hard_call", "pvalue"):
        return
    with np.nditer(data, flags=["external_loop", "buffered", "zerosize_ok"],
                   op_flags=["readonly"], buffersize=65536) as iterator:
        for block in iterator:
            # external_loop may yield an unbuffered contiguous array; slice it
            # again so temporary masks are always bounded by 64K elements.
            for start in range(0, block.size, 65536):
                values = block[start:start + 65536]
                code = info.get("missing_code", np.nan)
                missing = np.isnan(values) if check == "pvalue" or (isinstance(code, numbers.Real) and np.isnan(code)) else values == code
                values = values[~missing]
                high = 1 if check == "pvalue" else info.get("ploidy", 2)
                invalid = ~np.isfinite(values) | (values < 0) | (values > high)
                if check == "hard_call" or (check == "allele_count" and info.get("representation") == "hard_call"):
                    invalid |= values != np.floor(values)
                if invalid.any():
                    raise StepError(f"{where} contract: invalid {check} value {values[invalid][0]!r}")


def infer_output(rule, inputs, params):
    """Metadata transfer rules; never inspect or allocate a data tensor."""
    if not rule or rule.get("mode") == "unknown":
        return unknown()
    mode = rule["mode"]
    if mode == "declare":
        # A plugin can state a conservative, parameter-dependent output schema
        # without adding a named branch to the engine. Runtime checks promises.
        return {**unknown(), **resolve(deepcopy(rule.get("schema", {})), params)}
    result = deepcopy(inputs[0] if inputs else unknown())
    result.pop("reader", None)
    if mode == "project":
        keep = resolve(rule.get("keep_dims", result.get("dims")), params)
        if keep is None:
            return unknown()
        for axis, fields in list(result["axis_info"].items()):
            if axis not in keep:
                for key in fields:
                    result["info"].pop(key, None)
        result["axis_info"] = {d: f for d, f in result["axis_info"].items() if d in keep}
        result["labels"] = {d: f for d, f in result["labels"].items() if d in keep}
        result["dims"], result["ndim"] = keep, len(keep)
        if rule.get("derived", False):
            for key in ("representation", "ploidy", "alphabet", "encoders"):
                result["info"].pop(key, None)
    dims = result.get("dims")
    dim = params.get("dim")
    if mode == "subset" and dim:
        result["labels"][dim] = None
    elif mode == "select" and dim:
        result["labels"][dim] = params.get("labels") or None
    elif mode == "drop" and dim:
        known = result["labels"].get(dim)
        result["labels"][dim] = [v for v in known if v not in params.get("labels", [])] if known is not None else None
    elif mode == "rename":
        old, new = params.get("from"), params.get("to")
        if old and new:
            result["dims"] = [new if d == old else d for d in dims] if dims else None
            for key in ("labels", "axis_info"):
                if old in result[key]:
                    result[key][new] = result[key].pop(old)
    elif mode == "transpose":
        result["dims"] = params.get("order") or None
    elif mode == "transform":
        for key in ("ploidy", "representation", "encoders", "alphabet"):
            result["info"].pop(key, None)
        result["info"].update(missing_code=MISSING, representation={"type": "string", "const": rule["representation"]})
    elif mode in ("cox_regression", "logrank_test"):
        for fields in result["axis_info"].values():
            for key in fields:
                result["info"].pop(key, None)
        for key in ("ploidy", "representation", "encoders", "alphabet"):
            result["info"].pop(key, None)
        axis = "covariate" if mode == "cox_regression" else "comparison"
        columns = ["coef", "HR", "se", "z", "P", "CI_low", "CI_high"] if mode == "cox_regression" else ["chi2", "df", "P"]
        result.update(ndim=2, dims=[axis, "statistic"], labels={axis: None, "statistic": columns}, axis_info={})
        result["info"].update(missing_code=MISSING, representation={"type": "string", "const": mode})
    elif mode in ("pca", "regress", "compare_groups"):
        kept = next((d for d in dims or [] if d != dim), None) if mode == "pca" else dim
        added = "component" if mode == "pca" else "statistic"
        for axis, fields in list(result["axis_info"].items()):
            if axis != kept:
                for key in fields:
                    result["info"].pop(key, None)
                del result["axis_info"][axis]
        for key in ("ploidy", "representation", "encoders", "alphabet"):
            result["info"].pop(key, None)
        result["info"].update(missing_code=MISSING, representation={"type": "string", "const": "scores" if mode == "pca" else "comparison" if mode == "compare_groups" else "regression"})
        result.update(ndim=2, dims=[kept, added] if kept else None)
        # PCA clips n_components to matrix rank; actual count is not guaranteed.
        known = result["labels"].get(kept)
        if mode == "regress" and known is not None:
            known = [v for v in known if v not in [params.get("response"), *params.get("covariates", [])]]
        result["labels"] = {**({kept: known} if kept else {}), added: None if mode == "pca" else ["BETA", "SE", "P", "N"]}
        if mode == "compare_groups":
            result["labels"][added] = ["log2FC", "mean_a", "mean_b", "stat", "P", "N"] + (["Q_VALUE"] if params.get("method") == "deseq2" else [])
    elif mode == "correction":
        dim = params.get("dim", "statistic")
        known = result["labels"].get(dim)
        result["labels"][dim] = [*known, "Q_VALUE", "SIGNIFICANT"] if known is not None else None
        result["info"]["correction_method"] = {"type": "string", "const": params.get("method", "bonferroni")}
    elif mode == "attach":
        target = params.get("target_dim")
        fields = params.get("fields", [])
        if target and fields and len(inputs) > 1:
            for key in fields:
                result["info"][key] = {"type": "array"}
            result["axis_info"][target] = sorted(set(result["axis_info"].get(target, [])) | set(fields))
    elif mode == "concat":
        # Label intersections, missing annotations and scalar conflicts depend
        # on every input. Retain only common scalar guarantees at plan time.
        result["labels"] = {d: None for d in dims or []}
        result["axis_info"] = {}
        result["axis_info_open"] = True
        result["info"] = {key: value for key, value in result["info"].items()
                          if value.get("type") != "array" and all(other.get("info", {}).get(key) == value for other in inputs[1:])}
        result["info_open"] = any(other.get("info_open", True) for other in inputs)
        if "representation" not in result["info"]:
            result["info"].pop("ploidy", None)
    result["info"].update(deepcopy(rule.get("info", {})))
    if mode in {"subset", "select", "drop", "concat", "rename", "transpose", "attach"} and "encoders" in result["info"]:
        # Removing the last encoded field also removes its empty encoder map.
        result["info"]["encoders"]["optional"] = True
    return result


def validate_output(form, expected, where):
    """Check output promises before handing the Form to the cache manager."""
    required = {"numeric": expected.get("numeric", True), "info": expected.get("info", {}),
                "dims": expected.get("dims") or [], "labels": [], "parallel": []}
    if "ndim" in expected:
        required["ndim"] = expected["ndim"]
    for dim, labels in expected.get("labels", {}).items():
        if labels is not None:
            required["labels"].append({"dim": dim, "values": labels})
    for dim, fields in expected.get("axis_info", {}).items():
        required["parallel"].append({"dim": dim, "fields": fields})
    validate_form(form, required, where)
    if form.info.get("representation") in ("hard_call", "dosage"):
        validate_values(form.data, form.info, {"values": "allele_count"}, where)
    if expected.get("dims") is not None and form.dims != expected["dims"]:
        raise StepError(f"{where} contract: output dimension order differs from declaration")
