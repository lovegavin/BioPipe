"""Passing-Bablok regression for two measurement methods."""
from __future__ import annotations

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._stats20_common import scalar_form
from ._method33_common import method_pairs, passing_bablok


_NAMES = ["slope", "intercept", "n"]


class PassingBablokStep(Step):
    name = "passing_bablok"
    title = "Passing-Bablok regression"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "method_a": {"type": "string", "default": "method_a"},
            "method_b": {"type": "string", "default": "method_b"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        x, y = method_pairs(
            inputs[0],
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("method_a", "method_a"),
            ctx.step_params.get("method_b", "method_b"),
            "passing_bablok",
        )
        slope, intercept, n = passing_bablok(x, y)
        form = scalar_form([slope, intercept, float(n)], _NAMES, "passing_bablok")
        form.info.update({"method": "Passing-Bablok", "ci_method": "none", "n": n})
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"slope": slope, "intercept": intercept, "n": n}
        print(f"[passing_bablok] slope={slope:.6g} intercept={intercept:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
