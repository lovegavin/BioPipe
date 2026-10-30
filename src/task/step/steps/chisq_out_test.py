"""Chi-square test for a single outlier in a univariate sample."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ChiSquareOutTestStep(Step):
    """Chi-square test for one extreme observation.

    Mirrors ``outliers::chisq.out.test``: the farther of the minimum and
    maximum from the sample mean is tested with
    ``chi2 = (extreme - mean)^2 / variance`` on one degree of freedom.
    ``opposite`` forces the other extreme, as in the R implementation.
    """

    name = "chisq_out_test"
    title = "Chi-square outlier test"
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
            "variance": {"type": "number", "exclusiveMinimum": 0, "title": "已知方差（留空用样本方差）"},
            "opposite": {"type": "boolean", "default": False, "title": "检验另一端"},
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
        opposite = bool(ctx.step_params.get("opposite", False))
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, self.name)
        values = np.asarray(numeric_column(frame, value_label, self.name), dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3:
            raise StepError(f"{self.name}: need at least three observations")
        observed_variance = float(np.var(values, ddof=1))
        known = ctx.step_params.get("variance")
        variance = float(known) if known is not None else observed_variance
        if variance <= 0 or not np.isfinite(variance):
            raise StepError(f"{self.name}: variance must be positive and finite")
        mean = float(np.mean(values))
        low = float(values.min())
        high = float(values.max())
        use_low = bool((high - mean) < (mean - low)) != opposite
        if use_low:
            outlier = low
            direction = "low"
        else:
            outlier = high
            direction = "high"
        statistic = float((outlier - mean) ** 2 / variance)
        p_value = float(stats.chi2.sf(statistic, 1))
        out = scalar_form(
            [statistic, p_value, outlier, float(n)],
            ["statistic", "p", "outlier", "n"],
            self.name,
        )
        out.info.update(
            {
                "direction": direction,
                "variance": variance,
                "variance_source": "user" if known is not None else "sample",
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic,
            "p": p_value,
            "outlier": outlier,
            "direction": direction,
            "n": n,
            "variance": variance,
        }
        print(f"[{self.name}] chi2={statistic:.6f}, p={p_value:.6g}, {direction}={outlier:g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
