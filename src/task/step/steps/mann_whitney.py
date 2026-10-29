"""Mann-Whitney U test for exactly two groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class MannWhitneyStep(Step):
    name = "mann_whitney"
    title = "Mann-Whitney U test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
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
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(columns) != 2:
            from src.core import StepError
            raise StepError(f"mann_whitney needs exactly two groups, got {len(groups)}")
        rows = []
        for i in range(len(features)):
            u, p = stats.mannwhitneyu(
                columns[0][:, i], columns[1][:, i],
                alternative=ctx.step_params.get("alternative", "two-sided"),
            )
            rows.append([float(u), float(p)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)}, "statistic": {"U": 0, "P": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "groups": groups}
        print(f"[mann_whitney] {len(features)} features, groups={groups}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
