"""Per-sample summary metrics along a feature axis.

Input: any 2D Form with axes [feature_dim, sample_dim].

For each declared metric, a summary is computed along the feature
axis, producing one value per sample. A metric may restrict itself
to features whose label starts with a given prefix, and may divide
its raw result by another metric declared in the same call.

Metrics
-------
op values and their meaning over the selected feature subset:
    sum      sum of non-missing values
    mean     arithmetic mean of non-missing values
    std      population standard deviation (ddof=0)
    var      population variance (ddof=0)
    min      minimum of non-missing values
    max      maximum of non-missing values
    count    number of non-missing values
    nonzero  number of non-missing and non-zero values

Missing cells are recognised from info["missing_code"]: when that
code is NaN, non-finite cells count as missing.

Output:
    data   2D float32, shape (n_samples, n_metrics)
    dims   [sample_dim, statistic]
    statistic labels are the metric names, in declaration order.

Params:
    feature_dim : feature axis (default "feature")
    sample_dim  : sample axis  (default "sample")
    metrics     : list of {"name", "op", "feature_pattern"?, "divide_by"?}
    output      : context key (default: step name)
"""
from __future__ import annotations

import numbers
import warnings

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_OPS = ("sum", "mean", "std", "var", "min", "max", "count", "nonzero")


def _missing_mask(data, code):
    if isinstance(code, numbers.Real) and not isinstance(code, bool) and np.isnan(code):
        return ~np.isfinite(data)
    return data == code


def _apply_op(op, data, valid):
    """data and valid share shape (n_feature_subset, n_sample)."""
    if op == "count":
        return valid.sum(axis=0).astype(np.float64)
    if op == "nonzero":
        return ((data != 0) & valid).sum(axis=0).astype(np.float64)
    masked = np.where(valid, data, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if op == "sum":
            return np.nansum(masked, axis=0)
        if op == "mean":
            return np.nanmean(masked, axis=0)
        if op == "std":
            return np.nanstd(masked, axis=0)
        if op == "var":
            return np.nanvar(masked, axis=0)
        if op == "min":
            return np.nanmin(masked, axis=0)
        if op == "max":
            return np.nanmax(masked, axis=0)
    raise StepError(f"qc_metrics: unsupported op {op!r}")


class QcMetricsStep(Step):
    """Per-sample summary metrics along a feature axis."""

    name = "qc_metrics"
    category = "quality_control"
    icon = "CheckSquare"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "metrics": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "op": {"type": "string", "enum": list(_OPS)},
                        "feature_pattern": {"type": "string", "minLength": 1},
                        "divide_by": {"type": "string", "minLength": 1},
                    },
                    "required": ["name", "op"],
                    "additionalProperties": False,
                },
            },
            "output": {"type": "string"},
        },
        "required": ["metrics"],
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("feature_dim", "feature"),
              param("sample_dim", "sample")],
        info={"missing_code": MISSING},
    )]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        f_dim = ctx.step_params.get("feature_dim", "feature")
        s_dim = ctx.step_params.get("sample_dim", "sample")
        metrics = ctx.step_params.get("metrics")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != f_dim or form.dims[1] != s_dim:
            raise StepError(
                f"qc_metrics: expected 2D [{f_dim},{s_dim}], got {form.dims}"
            )
        if not isinstance(metrics, list) or not metrics:
            raise StepError("qc_metrics: 'metrics' must be a non-empty list")

        names = [m["name"] for m in metrics]
        if len(set(names)) != len(names):
            raise StepError("qc_metrics: metric names must be unique")
        name_set = set(names)
        for m in metrics:
            if "divide_by" in m and m["divide_by"] not in name_set:
                raise StepError(
                    f"qc_metrics: divide_by '{m['divide_by']}' is not one of "
                    f"the declared metric names {sorted(name_set)}"
                )

        data = form.data.astype(np.float64)
        missing = _missing_mask(data, form.info.get("missing_code", np.nan))
        valid_all = ~missing

        feature_labels = form.labels[f_dim]
        ordered_labels = [
            label for label, _ in sorted(feature_labels.items(), key=lambda kv: kv[1])
        ]

        raw: dict[str, np.ndarray] = {}
        for m in metrics:
            op = m["op"]
            pattern = m.get("feature_pattern")
            if pattern is not None:
                mask = np.array(
                    [str(lbl).startswith(pattern) for lbl in ordered_labels],
                    dtype=bool,
                )
                if not mask.any():
                    raise StepError(
                        f"qc_metrics: metric '{m['name']}' pattern "
                        f"'{pattern}' matched no feature labels"
                    )
                sub = data[mask]
                sub_valid = valid_all[mask]
            else:
                sub = data
                sub_valid = valid_all
            raw[m["name"]] = _apply_op(op, sub, sub_valid)

        columns = []
        for m in metrics:
            value = raw[m["name"]]
            if "divide_by" in m:
                denom = raw[m["divide_by"]]
                with np.errstate(invalid="ignore", divide="ignore"):
                    value = np.where(denom == 0, np.nan, value / denom)
            columns.append(value)

        out_data = np.stack(columns, axis=1).astype(np.float32)

        info, axis_info = project_metadata(
            form, keep_dims=[s_dim], derived=True,
        )
        info["missing_code"] = np.nan
        info["representation"] = "qc_metrics"

        out_form = Form(
            data=out_data,
            dims=[s_dim, "statistic"],
            labels={
                s_dim: dict(form.labels[s_dim]),
                "statistic": {n: i for i, n in enumerate(names)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "feature_dim": f_dim,
            "sample_dim": s_dim,
            "n_features": int(form.data.shape[0]),
            "n_samples": int(form.data.shape[1]),
            "metrics": [
                {
                    "name": m["name"],
                    "op": m["op"],
                    "feature_pattern": m.get("feature_pattern"),
                    "divide_by": m.get("divide_by"),
                }
                for m in metrics
            ],
            "per_metric_range": {
                m["name"]: [
                    float(np.nanmin(raw[m["name"]])) if np.isfinite(raw[m["name"]]).any() else None,
                    float(np.nanmax(raw[m["name"]])) if np.isfinite(raw[m["name"]]).any() else None,
                ]
                for m in metrics
            },
        }

        print(
            f"[qc_metrics] {form.data.shape[0]} features x "
            f"{form.data.shape[1]} samples, {len(metrics)} metrics"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
