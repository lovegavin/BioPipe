"""Cross-correlation function for two aligned series."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._timeseries63_common import aligned_series


class CrossCorrelationStep(Step):
    name = "cross_correlation"
    title = "Cross-correlation function"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "scipy>=1.10"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "first_label": {"type": "string"},
            "second_label": {"type": "string"},
            "lags": {"type": "integer", "minimum": 1, "default": 10},
            "alpha": {"type": "number", "minimum": 0.001, "maximum": 0.5, "default": 0.05},
            "output": {"type": "string"},
        },
        "required": ["first_label", "second_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        first_label = ctx.step_params["first_label"]
        second_label = ctx.step_params["second_label"]
        lags = int(ctx.step_params.get("lags", 10))
        alpha = float(ctx.step_params.get("alpha", 0.05))
        out_name = ctx.step_params.get("output", self.name)
        x, y = aligned_series(inputs[0], inputs[1], sample_dim, feature_dim, first_label, second_label, self.name)
        n = int(x.size)
        if lags < 1:
            raise StepError("cross_correlation: lags must be at least 1")
        if lags >= n:
            raise StepError("cross_correlation: lags must be less than n")
        if float(np.var(x)) <= 0 or float(np.var(y)) <= 0:
            raise StepError("cross_correlation: both series need variation")
        mx = float(x.mean())
        my = float(y.mean())
        sx = float(x.std(ddof=0))
        sy = float(y.std(ddof=0))
        rows = []
        labels = {}
        values = []
        for lag in range(-lags, lags + 1):
            if lag >= 0:
                left = x[lag:]
                right = y[: n - lag]
            else:
                left = x[: n + lag]
                right = y[-lag:]
            ccf = float(np.sum((left - mx) * (right - my)) / (n * sx * sy))
            rows.append([ccf, -norm.ppf(1 - alpha / 2) / np.sqrt(n), norm.ppf(1 - alpha / 2) / np.sqrt(n)])
            labels[str(lag)] = lag + lags
            values.append((lag, ccf))
        form = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["lag", "statistic"],
            labels={
                "lag": labels,
                "statistic": {"ccf": 0, "ci_lower": 1, "ci_upper": 2},
            },
            info={
                "missing_code": np.nan,
                "method": "pearson_lag_correlation",
                "n": n,
                "lags": lags,
                "alpha": alpha,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n": n,
            "lags": lags,
            "alpha": alpha,
            "ccf": [{"lag": lag, "ccf": value} for lag, value in values],
        }
        print(f"[{self.name}] n={n}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
