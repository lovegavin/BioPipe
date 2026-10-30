"""Benjamini-Yekutieli FDR adjustment."""
from __future__ import annotations

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._p_adjust_common import adjust


class ByAdjustStep(Step):
    """Benjamini-Yekutieli p-value adjustment; output feature x qvalue."""

    name = "by_adjust"
    title = "Benjamini-Yekutieli FDR"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("feature_dim", "feature"), param("value_dim", "statistic")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "value_dim": {"type": "string", "default": "pvalue"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        self._export_data = adjust(
            inputs[0], "by",
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("value_dim", "pvalue"),
            self.name, ctx, self.name,
        )
        print(f"[by_adjust] {self._export_data['n_tests']} tests")

    def export(self, ctx: Context) -> dict:
        return self._export_data
