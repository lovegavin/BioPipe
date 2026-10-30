"""Eta-squared effect size from one-way group means."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class EtaSquaredStep(Step):
    """Per-feature eta-squared, the between-group share of total variance."""

    name = "eta_squared"
    title = "Eta squared"
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
        rows = []
        for i in range(len(features)):
            values = [col[:, i] for col in columns]
            all_values = np.concatenate(values)
            grand = float(np.mean(all_values))
            ss_total = float(np.sum((all_values - grand) ** 2))
            ss_between = float(sum(len(v) * (np.mean(v) - grand) ** 2 for v in values))
            rows.append([ss_between / ss_total if ss_total > 0 else float("nan")])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"eta2": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": len(groups)}
        print(f"[eta_squared] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data
