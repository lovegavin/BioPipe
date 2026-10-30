"""Anscombe-Glynn kurtosis test for univariate normality."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class AnscombeGlynnStep(Step):
    """Anscombe-Glynn test for sample kurtosis."""

    name = "anscombe_glynn"
    title = "Anscombe-Glynn kurtosis test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string", "title": "数值字段"},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "greater", "less"],
                "default": "two-sided",
            },
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
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 8 or n > 46340:
            raise StepError("anscombe_glynn: sample size must be between 8 and 46340")
        centered = values - float(values.mean())
        m2 = float(np.mean(centered * centered))
        if m2 <= 0:
            raise StepError("anscombe_glynn: values have zero variance")
        kurt = float(np.mean(centered ** 4) / (m2 * m2))
        expected = 3.0 * (n - 1.0) / (n + 1.0)
        variance = (
            24.0 * n * (n - 2.0) * (n - 3.0)
            / ((n + 1.0) ** 2 * (n + 3.0) * (n + 5.0))
        )
        if variance <= 0:
            raise StepError("anscombe_glynn: sample size is too small")
        m3 = (
            6.0 * (n * n - 5.0 * n + 2.0) / ((n + 7.0) * (n + 9.0))
            * np.sqrt(6.0 * (n + 3.0) * (n + 5.0) / (n * (n - 2.0) * (n - 3.0)))
        )
        a = 6.0 + (8.0 / m3) * (2.0 / m3 + np.sqrt(1.0 + 4.0 / (m3 * m3)))
        xx = (kurt - expected) / np.sqrt(variance)
        z = (
            1.0
            - 2.0 / (9.0 * a)
            - ((1.0 - 2.0 / a) / (1.0 + xx * np.sqrt(2.0 / (a - 4.0)))) ** (1.0 / 3.0)
        ) / np.sqrt(2.0 / (9.0 * a))
        if alternative == "greater":
            p_value = float(stats.norm.sf(z))
        elif alternative == "less":
            p_value = float(stats.norm.cdf(z))
        else:
            p_value = 2.0 * float(stats.norm.sf(z))
            if p_value > 1.0:
                p_value = 2.0 - p_value
        out = scalar_form([kurt, z, p_value, float(n)], ["kurt", "z", "p", "n"], self.name)
        out.info.update({"alternative": alternative, "method": "Anscombe-Glynn kurtosis"})
        ctx[out_name] = out
        self._export_data = {
            "kurt": kurt,
            "z": z,
            "p": p_value,
            "n": n,
            "alternative": alternative,
        }
        print(f"[{self.name}] kurt={kurt:.6f}, z={z:.6f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
