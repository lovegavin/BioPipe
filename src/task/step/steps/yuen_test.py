"""Yuen's two-sample trimmed-mean test."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form
from ._tests39_common import select_groups, yuen_columns


class YuenTestStep(Step):
    name = "yuen_test"
    title = "Yuen trimmed-mean test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "group_a": {"type": "string"},
            "group_b": {"type": "string"},
            "trim": {"type": "number", "minimum": 0, "exclusiveMaximum": 0.5, "default": 0.2},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        trim = float(ctx.step_params.get("trim", 0.2))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        data, codes, _samples, group_a, group_b = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"], ctx.step_params["group_a"], ctx.step_params["group_b"],
            "yuen_test",
        )
        features = labels_in_order(expr, feature_dim)
        columns = ["diff", "t", "df", "p", "ci_low", "ci_high", "mean_a", "mean_b", "n_a", "n_b"]
        rows = []
        for j in range(data.shape[1]):
            values = yuen_columns(data[codes == 0, j], data[codes == 1, j], trim, confidence)
            if values is None:
                rows.append([np.nan] * len(columns))
            else:
                rows.append(values)
        if not any(np.isfinite(row[0]) for row in rows):
            raise StepError("yuen_test: no feature has enough finite observations")
        out = make_form(
            np.asarray(rows, dtype=np.float64),
            [feature_dim, "statistic"],
            {feature_dim: {name: i for i, name in enumerate(features)},
             "statistic": {name: i for i, name in enumerate(columns)}},
        )
        out.info.update({"group_a": group_a, "group_b": group_b, "trim": trim, "confidence": confidence})
        ctx[out_name] = out
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "trim": trim,
            "confidence": confidence, "n_features": len(features),
        }
        print(f"[yuen_test] features={len(features)} trim={trim:g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
