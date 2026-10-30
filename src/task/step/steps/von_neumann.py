"""Von Neumann successive-difference test for randomness."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class VonNeumannStep(Step):
    """Von Neumann ratio test for serial randomness."""

    name = "von_neumann"
    title = "Von Neumann randomness test"
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
            "alternative": {"type": "string", "enum": ["two.sided", "less", "greater"], "default": "two.sided"},
            "unbiased": {"type": "boolean", "default": True},
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
        alternative = ctx.step_params.get("alternative", "two.sided")
        unbiased = bool(ctx.step_params.get("unbiased", True))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "von_neumann")
        values = numeric_column(frame, value_label, "von_neumann")
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3:
            raise StepError("von_neumann: sample size must be at least 3")
        centered = values - float(values.mean())
        denominator = float(np.sum(centered * centered))
        if denominator <= 0:
            raise StepError("von_neumann: values have zero variance")
        ratio = float(np.sum(np.diff(values) ** 2) / denominator)
        if unbiased:
            vn = ratio * n / (n - 1)
            expected = 2.0 * n / (n - 1)
            variance = 4.0 * n * n * (n - 2.0) / ((n + 1.0) * (n - 1.0) ** 3)
        else:
            vn = ratio
            expected = 2.0
            variance = 4.0 * (n - 2.0) / (n * n - 1.0)
        z_unbiased = float((vn - expected) / np.sqrt(variance))
        p_unbiased = _p_value(z_unbiased, alternative)
        out = scalar_form(
            [vn, z_unbiased, p_unbiased, float(n)],
            ["VN", "z", "p", "n"],
            "von_neumann",
        )
        out.info.update({"alternative": alternative, "unbiased": unbiased})
        ctx[out_name] = out
        self._export_data = {
            "VN": vn, "z": z_unbiased, "p": p_unbiased, "n": n,
            "expected": expected, "variance": variance,
            "alternative": alternative, "unbiased": unbiased,
        }
        print(f"[von_neumann] VN={vn:.6f}, z={z_unbiased:.6f}, p={p_unbiased:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _p_value(z_value: float, alternative: str) -> float:
    if alternative == "less":
        return float(stats.norm.cdf(z_value))
    if alternative == "greater":
        return float(stats.norm.sf(z_value))
    return float(2.0 * stats.norm.sf(abs(z_value)))
