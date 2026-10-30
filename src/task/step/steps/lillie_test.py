"""Lilliefors test for normality."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class LillieTestStep(Step):
    """Lilliefors (Kolmogorov-Smirnov) normality test."""

    name = "lillie_test"
    title = "Lilliefors normality test"
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
        frame = table_frame(form, sample_dim, feature_dim, "lillie_test")
        values = np.sort(numeric_column(frame, value_label, "lillie_test"))
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 5:
            raise StepError("lillie_test: sample size must be at least 5")
        mean = float(values.mean())
        std = float(values.std(ddof=1))
        if std <= 0:
            raise StepError("lillie_test: values have zero variance")
        p_std = stats.norm.cdf((values - mean) / std)
        index = np.arange(1, n + 1, dtype=float)
        d_plus = float(np.max(index / n - p_std))
        d_minus = float(np.max(p_std - (index - 1.0) / n))
        d_value = max(d_plus, d_minus)
        if n <= 100:
            kd = d_value
            nd = n
        else:
            kd = d_value * ((n / 100.0) ** 0.49)
            nd = 100
        p_value = float(np.exp(
            -7.01256 * kd * kd * (nd + 2.78019)
            + 2.99587 * kd * np.sqrt(nd + 2.78019)
            - 0.122119 + 0.974598 / np.sqrt(nd) + 1.67997 / nd
        ))
        if p_value > 0.1:
            kk = (np.sqrt(n) - 0.01 + 0.85 / np.sqrt(n)) * d_value
            if kk <= 0.302:
                p_value = 1.0
            elif kk <= 0.5:
                p_value = 2.76773 - 19.828315 * kk + 80.709644 * kk ** 2 - 138.55152 * kk ** 3 + 81.218052 * kk ** 4
            elif kk <= 0.9:
                p_value = -4.901232 + 40.662806 * kk - 97.490286 * kk ** 2 + 94.029866 * kk ** 3 - 32.355711 * kk ** 4
            elif kk <= 1.31:
                p_value = 6.198765 - 19.558097 * kk + 23.186922 * kk ** 2 - 12.234627 * kk ** 3 + 2.423045 * kk ** 4
            else:
                p_value = 0.0
        p_value = float(p_value)
        out = scalar_form([d_value, p_value, float(n)], ["D", "p", "n"], "lillie_test")
        out.info.update({"method": "lilliefors", "p_method": "Dallal-Wilkinson"})
        ctx[out_name] = out
        self._export_data = {"D": d_value, "p": p_value, "n": n}
        print(f"[lillie_test] D={d_value:.8f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
