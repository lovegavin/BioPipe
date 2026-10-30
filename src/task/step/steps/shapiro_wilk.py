"""Shapiro-Wilk normality test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ShapiroWilkStep(Step):
    """Shapiro-Wilk W test for univariate normality."""

    name = "shapiro_wilk"
    title = "Shapiro-Wilk normality test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string", "title": "数值字段"},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "shapiro_wilk")
        values = numeric_column(frame, value_label, "shapiro_wilk")
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3 or n > 5000:
            raise StepError("shapiro_wilk: sample size must be between 3 and 5000")
        if float(np.var(values)) <= 0:
            raise StepError("shapiro_wilk: values have zero variance")
        result = stats.shapiro(values)
        w = float(result.statistic)
        p_value = float(result.pvalue)
        out = scalar_form([w, p_value, float(n)], ["W", "p", "n"], "shapiro_wilk")
        out.info.update({"method": "shapiro-wilk", "approximation": "AS R94"})
        ctx[out_name] = out
        self._export_data = {"W": w, "p": p_value, "n": n}
        print(f"[shapiro_wilk] W={w:.8f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
