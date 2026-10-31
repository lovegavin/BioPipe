"""Risk ratio with a Wald log-scale confidence interval."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._epi64_common import corrected_table, count_table, risk_ratio


class RiskRatioStep(Step):
    name = "risk_ratio"
    title = "Risk ratio"
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
        result = risk_ratio(table, float(ctx.step_params.get("confidence", 0.95)))
        stats = [result["rr"], result["ci_lower"], result["ci_upper"], result["p1"], result["p2"], result["n"]]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([stats], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"risk_ratio": 0},
                "statistic": {
                    "risk_ratio": 0,
                    "ci_lower": 1,
                    "ci_upper": 2,
                    "p_exposed": 3,
                    "p_unexposed": 4,
                    "n": 5,
                },
            },
            info={"missing_code": np.nan, "correction": "haldane" if corrected else "none"},
        )
        self._export_data = {
            "risk_ratio": result["rr"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "p_exposed": result["p1"],
            "p_unexposed": result["p2"],
            "n": int(result["n"]),
            "correction": "haldane" if corrected else "none",
        }
        print(f"[risk_ratio] rr={result['rr']:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
