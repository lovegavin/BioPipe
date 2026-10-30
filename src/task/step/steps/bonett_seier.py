"""Bonett-Seier test for Geary kurtosis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BonettSeierStep(Step):
    """Bonett-Seier test that Geary kurtosis equals sqrt(2/pi)."""

    name = "bonett_seier"
    title = "Bonett-Seier Geary kurtosis test"
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
        if n < 3:
            raise StepError("bonett_seier: sample size must be at least 3")
        centered = values - float(values.mean())
        rho = float(np.sqrt(np.mean(centered * centered)))
        tau = float(np.mean(np.abs(centered)))
        if rho <= 0 or tau <= 0:
            raise StepError("bonett_seier: values have zero variance")
        omega = 13.29 * (np.log(rho) - np.log(tau))
        z = float(np.sqrt(n + 2.0) * (omega - 3.0) / 3.54)
        if alternative == "greater":
            p_value = float(stats.norm.sf(z))
        elif alternative == "less":
            p_value = float(stats.norm.cdf(z))
        else:
            p_value = 2.0 * float(stats.norm.sf(z))
            if p_value > 1.0:
                p_value = 2.0 - p_value
        out = scalar_form([tau, z, p_value, float(n)], ["tau", "z", "p", "n"], self.name)
        out.info.update({"alternative": alternative, "method": "Bonett-Seier Geary kurtosis"})
        ctx[out_name] = out
        self._export_data = {
            "tau": tau,
            "z": z,
            "p": p_value,
            "n": n,
            "alternative": alternative,
        }
        print(f"[{self.name}] tau={tau:.6f}, z={z:.6f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
