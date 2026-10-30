"""Cohen's d and Hedges' g for exactly two groups."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class CohensDStep(Step):
    """Per-feature standardized mean difference between two groups."""

    name = "cohens_d"
    title = "Cohen's d"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        columns, features, groups = grouped(
            data, meta,
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("group_dim", "sample"),
            ctx.step_params["group_label"],
        )
        if len(groups) != 2:
            raise StepError("cohens_d needs exactly two groups")
        rows = []
        for i in range(len(features)):
            a, b = columns[0][:, i], columns[1][:, i]
            n1, n2 = len(a), len(b)
            var = ((n1 - 1) * np.var(a, ddof=1) + (n2 - 1) * np.var(b, ddof=1)) / (n1 + n2 - 2)
            if var <= 0:
                d = 0.0 if abs(np.mean(a) - np.mean(b)) < 1e-15 else float("nan")
            else:
                d = float((np.mean(a) - np.mean(b)) / np.sqrt(var))
            g = float(d * (1.0 - 3.0 / (4.0 * (n1 + n2) - 9.0))) if np.isfinite(d) else float("nan")
            rows.append([d, g])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"d": 0, "hedges_g": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": 2, "group0": int(groups[0]), "group1": int(groups[1])}
        print(f"[cohens_d] {len(features)} features, 2 groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data
