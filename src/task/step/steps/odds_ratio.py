"""Odds ratio with a Woolf log-scale confidence interval."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._epi64_common import corrected_table, count_table, odds_ratio


class OddsRatioStep(Step):
    name = "odds_ratio"
    title = "Odds ratio"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("row_dim", "row"), param("col_dim", "col")])]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "row"},
            "col_dim": {"type": "string", "default": "col"},
            "correction": {"type": "string", "enum": ["none", "haldane"], "default": "haldane"},
            "confidence": {"type": "number", "default": 0.95, "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        table = count_table(
            inputs[0],
            ctx.step_params.get("row_dim", "row"),
            ctx.step_params.get("col_dim", "col"),
            self.name,
        )
        table, corrected = corrected_table(
            table, ctx.step_params.get("correction", "haldane"), self.name
        )
        result = odds_ratio(table, float(ctx.step_params.get("confidence", 0.95)))
        stats = [
            result["odds_ratio"],
            result["ci_lower"],
            result["ci_upper"],
            result["log_or"],
            result["se"],
            result["n"],
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([stats], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"odds_ratio": 0},
                "statistic": {
                    "odds_ratio": 0,
                    "ci_lower": 1,
                    "ci_upper": 2,
                    "log_or": 3,
                    "se": 4,
                    "n": 5,
                },
            },
            info={"missing_code": np.nan, "correction": "haldane" if corrected else "none"},
        )
        self._export_data = {
            "odds_ratio": result["odds_ratio"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "log_or": result["log_or"],
            "se": result["se"],
            "n": int(result["n"]),
            "correction": "haldane" if corrected else "none",
        }
        print(f"[odds_ratio] or={result['odds_ratio']:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
