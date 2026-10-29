"""Fisher exact test for a 2x2 contingency table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class FisherExactStep(Step):
    name = "fisher_exact"
    title = "Fisher exact test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("row_dim", "row"), param("col_dim", "col")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "row"},
            "col_dim": {"type": "string", "default": "col"},
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        table = np.asarray(inputs[0].data, dtype=np.float64)
        if table.shape != (2, 2):
            raise StepError(f"fisher_exact needs a 2x2 table, got {table.shape}")
        if (table < 0).any():
            raise StepError("fisher_exact requires non-negative counts")
        odds, p = stats.fisher_exact(table, alternative=ctx.step_params.get("alternative", "two-sided"))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[odds, p]], dtype=np.float32),
            dims=["metric", "statistic"],
            labels={"metric": {"fisher_exact": 0}, "statistic": {"odds_ratio": 0, "P": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"odds_ratio": float(odds), "p": float(p)}
        print(f"[fisher_exact] odds_ratio={odds:.3f}, p={p:.3g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
