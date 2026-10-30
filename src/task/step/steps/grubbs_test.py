"""Grubbs test for a single outlier in a univariate sample."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class GrubbsTestStep(Step):
    """Grubbs (extreme studentized deviate) test for one outlier.

    The most extreme observation (largest absolute deviation from the sample
    mean) is tested against the two-sided Grubbs statistic. The p-value uses
    the Student-t form of the Grubbs distribution, matching
    ``outliers::grubbs.test(type = 10)``; ``two_sided`` doubles the
    one-sided tail exactly as that implementation does.
    """

    name = "grubbs_test"
    title = "Grubbs outlier test"
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
            "two_sided": {"type": "boolean", "default": False, "title": "双侧 p 值"},
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
        two_sided = bool(ctx.step_params.get("two_sided", False))
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "grubbs_test")
        values = np.asarray(numeric_column(frame, value_label, "grubbs_test"), dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3:
            raise StepError("grubbs_test: need at least three observations")
        mean = float(np.mean(values))
        sd = float(np.std(values, ddof=1))
        if sd <= 0 or not np.isfinite(sd):
            raise StepError("grubbs_test: values have zero variance")

        low = float(values.min())
        high = float(values.max())
        if (high - mean) >= (mean - low):
            outlier_index = int(np.argmax(values))
            direction = "high"
        else:
            outlier_index = int(np.argmin(values))
            direction = "low"
        outlier = float(values[outlier_index])
        rest = np.delete(values, outlier_index)
        if rest.size < 2:
            raise StepError("grubbs_test: need at least two non-outlier observations")

        g_value = abs(outlier - mean) / sd
        u_value = float(np.var(rest, ddof=1) / np.var(values, ddof=1) * (n - 2) / (n - 1))
        denominator = (n - 1.0) ** 2 - n * g_value ** 2
        if denominator <= 0:
            p_one = 0.0
        else:
            t_value = np.sqrt(n * (n - 2.0) * g_value ** 2 / denominator)
            p_one = min(1.0, n * float(stats.t.sf(t_value, n - 2)))
        p_value = 2.0 * p_one if two_sided else p_one
        if two_sided and p_value > 1.0:
            p_value = 2.0 - p_value
        p_value = min(max(float(p_value), 0.0), 1.0)

        out = scalar_form(
            [g_value, u_value, p_value, outlier, float(n)],
            ["G", "U", "p", "outlier", "n"],
            "grubbs_test",
        )
        out.info.update({"direction": direction, "two_sided": two_sided, "method": "Grubbs extreme studentized deviate"})
        ctx[out_name] = out
        self._export_data = {
            "G": g_value, "U": u_value, "p": p_value, "outlier": outlier,
            "direction": direction, "n": n, "two_sided": two_sided,
        }
        print(f"[grubbs_test] G={g_value:.6f}, p={p_value:.6g}, {direction}={outlier:g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
