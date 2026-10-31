"""F test for the ratio of two independent variances."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._metric_common import score_series


class VarianceRatioStep(Step):
    name = "variance_ratio"
    title = "Variance ratio F test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("value_dim", "value")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("value_dim", "value")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "value_dim": {"type": "string", "default": "value"},
            "first_label": {"type": "string"},
            "second_label": {"type": "string"},
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "confidence": {"type": "number", "default": 0.95, "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        value_dim = ctx.step_params.get("value_dim", "value")
        first_label = ctx.step_params.get("first_label") or next(iter(inputs[0].labels[value_dim]))
        second_label = ctx.step_params.get("second_label") or next(iter(inputs[1].labels[value_dim]))
        _, first = score_series(inputs[0], sample_dim, value_dim, first_label)
        _, second = score_series(inputs[1], sample_dim, value_dim, second_label)
        first = first[np.isfinite(first)]
        second = second[np.isfinite(second)]
        if first.size < 2 or second.size < 2:
            raise StepError("variance_ratio: each sample needs at least two finite values")
        var1 = float(np.var(first, ddof=1))
        var2 = float(np.var(second, ddof=1))
        if var1 <= 0 or var2 <= 0:
            raise StepError("variance_ratio: both samples must have positive variance")
        ratio = var1 / var2
        df1 = first.size - 1
        df2 = second.size - 1
        alternative = ctx.step_params.get("alternative", "two-sided")
        if alternative == "less":
            p = float(stats.f.cdf(ratio, df1, df2))
        elif alternative == "greater":
            p = float(stats.f.sf(ratio, df1, df2))
        else:
            p = float(min(1.0, 2.0 * min(stats.f.cdf(ratio, df1, df2), stats.f.sf(ratio, df1, df2))))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        if not 0.0 < confidence < 1.0:
            raise StepError("variance_ratio: confidence must be between 0 and 1")
        alpha = 1.0 - confidence
        ci_lower = ratio / float(stats.f.ppf(1.0 - alpha / 2.0, df1, df2))
        ci_upper = ratio / float(stats.f.ppf(alpha / 2.0, df1, df2))
        data = np.asarray([[ratio, df1, df2, p, ci_lower, ci_upper, first.size, second.size]], dtype=np.float64)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["metric", "statistic"],
            labels={
                "metric": {"variance_ratio": 0},
                "statistic": {
                    "ratio": 0,
                    "df1": 1,
                    "df2": 2,
                    "p": 3,
                    "ci_lower": 4,
                    "ci_upper": 5,
                    "n1": 6,
                    "n2": 7,
                },
            },
            info={"missing_code": np.nan, "alternative": alternative, "confidence": confidence},
        )
        self._export_data = {
            "ratio": ratio,
            "df1": int(df1),
            "df2": int(df2),
            "p": p,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n1": int(first.size),
            "n2": int(second.size),
        }
        print(f"[variance_ratio] F={ratio:.4g}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
