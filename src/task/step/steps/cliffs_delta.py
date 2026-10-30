"""Cliff's delta effect size for exactly two groups."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class CliffsDeltaStep(Step):
    """Per-feature Cliff's delta, positive when group0 tends larger."""

    name = "cliffs_delta"
    title = "Cliff's delta"
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
            raise StepError("cliffs_delta needs exactly two groups")
        rows = []
        for i in range(len(features)):
            a, b = columns[0][:, i], columns[1][:, i]
            delta = float((np.sum(a[:, None] > b[None, :]) - np.sum(a[:, None] < b[None, :])) / (len(a) * len(b)))
            rows.append([delta])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"delta": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": 2}
        print(f"[cliffs_delta] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
