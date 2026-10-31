"""Cohen's h effect size for two independent proportions."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._epi64_common import cohens_h, count_table


class CohensHStep(Step):
    name = "cohens_h"
    title = "Cohen's h"
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
        result = cohens_h(table, float(ctx.step_params.get("confidence", 0.95)))
        stats = [
            result["h"],
            result["ci_lower"],
            result["ci_upper"],
            result["p1"],
            result["p2"],
            result["n1"],
            result["n2"],
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([stats], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"cohens_h": 0},
                "statistic": {
                    "cohens_h": 0,
                    "ci_lower": 1,
                    "ci_upper": 2,
                    "p1": 3,
                    "p2": 4,
                    "n1": 5,
                    "n2": 6,
                },
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "cohens_h": result["h"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "p1": result["p1"],
            "p2": result["p2"],
            "n1": int(result["n1"]),
            "n2": int(result["n2"]),
        }
        print(f"[cohens_h] h={result['h']:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
