"""D'Agostino skewness test for univariate normality."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class AgostinoSkewnessStep(Step):
    """D'Agostino test for sample skewness."""

    name = "agostino_skewness"
    title = "D'Agostino skewness test"
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
                "enum": ["two-sided", "positive", "negative"],
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
            raise StepError("agostino_skewness: sample size must be between 8 and 46340")
        centered = values - float(values.mean())
        m2 = float(np.mean(centered * centered))
        if m2 <= 0:
            raise StepError("agostino_skewness: values have zero variance")
        skew = float(np.mean(centered ** 3) / m2 ** 1.5)
        y = skew * np.sqrt((n + 1.0) * (n + 3.0) / (6.0 * (n - 2.0)))
        b2 = (
            3.0
            * (n * n + 27.0 * n - 70.0)
            * (n + 1.0)
            * (n + 3.0)
            / ((n - 2.0) * (n + 5.0) * (n + 7.0) * (n + 9.0))
        )
        w = np.sqrt(-1.0 + np.sqrt(2.0 * (b2 - 1.0)))
        d = 1.0 / np.sqrt(np.log(w))
        a = np.sqrt(2.0 / (w * w - 1.0))
        z = float(d * np.log(y / a + np.sqrt((y / a) ** 2 + 1.0)))
        if alternative == "positive":
            p_value = float(stats.norm.sf(z))
        elif alternative == "negative":
            p_value = float(stats.norm.cdf(z))
        else:
            p_value = float(2.0 * min(stats.norm.sf(z), stats.norm.cdf(z)))
        out = scalar_form([skew, z, p_value, float(n)], ["skew", "z", "p", "n"], self.name)
        out.info.update({"alternative": alternative, "method": "D'Agostino skewness"})
        ctx[out_name] = out
        self._export_data = {
            "skew": skew,
            "z": z,
            "p": p_value,
            "n": n,
            "alternative": alternative,
        }
        print(f"[{self.name}] skew={skew:.6f}, z={z:.6f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
