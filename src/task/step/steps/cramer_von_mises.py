"""Two-sample Cramer-von Mises test for exactly two groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class CramerVonMisesStep(Step):
    """Per-feature two-sample Cramer-von Mises test."""

    name = "cramer_von_mises"
    title = "Cramer-von Mises test"
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
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
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
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) != 2:
            raise StepError("cramer_von_mises needs exactly two groups")
        rows = []
        for i in range(len(features)):
            a = columns[0][:, i]
            b = columns[1][:, i]
            try:
                result = stats.cramervonmises_2samp(a, b)
                rows.append([float(result.statistic), float(result.pvalue)])
            except (ValueError, TypeError):
                rows.append([float("nan"), float("nan")])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"W": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": len(groups), "method": "cramer_von_mises"}
        print(f"[cramer_von_mises] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data
