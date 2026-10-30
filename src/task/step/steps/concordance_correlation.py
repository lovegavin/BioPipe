"""Lin's concordance correlation coefficient, ported from DescTools::CCC."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._stats20_common import scalar_form
from ._agreement32_common import paired_columns


_NAMES = [
    "ccc", "se", "ci_low", "ci_high", "z", "p", "t",
    "s_shift", "l_shift", "c_bias", "mean_diff", "sd_diff", "n",
]


class ConcordanceCorrelationStep(Step):
    name = "concordance_correlation"
    title = "Lin's concordance correlation"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.10"]
    dependency_imports = ["scipy"]
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
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        name = "concordance_correlation"
        x, y = paired_columns(
            inputs[0],
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("method_a", "method_a"),
            ctx.step_params.get("method_b", "method_b"),
            name,
        )
        n = x.size
        xb, yb = float(np.mean(x)), float(np.mean(y))
        sx2 = float(np.var(x, ddof=1) * (n - 1) / n)
        sy2 = float(np.var(y, ddof=1) * (n - 1) / n)
        sd_x, sd_y = float(np.std(x, ddof=1)), float(np.std(y, ddof=1))
        r = float(np.corrcoef(x, y)[0, 1])
        if not np.isfinite(r) or abs(r) < 1e-15:
            raise StepError(f"{name}: Pearson correlation is zero; CCC is undefined")
        sxy = r * np.sqrt(sx2 * sy2)
        ccc = 2.0 * sxy / (sx2 + sy2 + (yb - xb) ** 2)
        if not np.isfinite(ccc) or abs(ccc) >= 1.0:
            raise StepError(f"{name}: CCC is at the boundary ±1; standard error is undefined")
        s_shift = sd_y / sd_x
        u = (yb - xb) / ((sx2 * sy2) ** 0.25)
        c_bias = ccc / r
        numerator = (
            (1.0 - r * r) * ccc * ccc * (1.0 - ccc * ccc) / (r * r)
            + 2.0 * ccc ** 3 * (1.0 - ccc) * u * u / r
            - 0.5 * ccc ** 4 * u ** 4 / (r * r)
        )
        se = float(np.sqrt(max(0.0, numerator) / (n - 2)))
        alpha = 1.0 - float(ctx.step_params.get("confidence", 0.95))
        zcrit = float(stats.norm.ppf(1.0 - alpha / 2.0))
        z_value = float(np.arctanh(ccc))
        z_se = se / (1.0 - ccc * ccc)
        ci_low = float(np.tanh(z_value - zcrit * z_se))
        ci_high = float(np.tanh(z_value + zcrit * z_se))
        t_value = float(ccc * np.sqrt((n - 2.0) / (1.0 - ccc * ccc)))
        p_value = float(2.0 * stats.t.sf(abs(t_value), n - 2))

        values = [
            ccc, se, ci_low, ci_high, z_value, p_value, t_value,
            s_shift, u, c_bias, float(np.mean(y - x)), float(np.std(y - x, ddof=1)), float(n),
        ]
        form = scalar_form(values, _NAMES, name)
        form.info.update({
            "method": "Lin's CCC",
            "confidence": float(ctx.step_params.get("confidence", 0.95)),
            "ci_method": "z-transform",
        })
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "ccc": ccc, "se": se, "ci_low": ci_low, "ci_high": ci_high,
            "p": p_value, "s_shift": s_shift, "l_shift": u, "c_bias": c_bias, "n": int(n),
        }
        print(f"[concordance_correlation] ccc={ccc:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
