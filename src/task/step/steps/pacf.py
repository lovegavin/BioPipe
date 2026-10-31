"""Partial autocorrelation function for a univariate series."""
from __future__ import annotations

import numpy as np
from scipy import stats
from statsmodels.tsa.stattools import pacf

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class PacfStep(Step):
    name = "pacf"
    title = "Partial autocorrelation function"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string"},
            "lags": {"type": "integer", "minimum": 1, "default": 10},
            "alpha": {"type": "number", "minimum": 0.001, "maximum": 0.5, "default": 0.05},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = int(ctx.step_params.get("lags", 10))
        alpha = float(ctx.step_params.get("alpha", 0.05))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if lags < 1:
            raise StepError("pacf: lags must be at least 1")
        if lags >= n:
            raise StepError("pacf: lags must be less than n")
        if float(np.var(values)) <= 0:
            raise StepError("pacf: series has no variation")
        estimate = pacf(values, nlags=lags, method="ywm")
        z = float(stats.norm.ppf(1.0 - alpha / 2.0))
        width = z / np.sqrt(n)
        rows = []
        labels = {}
        for lag in range(1, lags + 1):
            rows.append([float(estimate[lag]), -width, width])
            labels[str(lag)] = lag - 1
        form = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["lag", "statistic"],
            labels={"lag": labels, "statistic": {"pacf": 0, "ci_lower": 1, "ci_upper": 2}},
            info={
                "missing_code": np.nan,
                "method": "statsmodels_pacf_ywm",
                "alpha": alpha,
                "n": n,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n": n,
            "lags": lags,
            "alpha": alpha,
            "pacf": [float(v) for v in estimate[1:]],
        }
        print(f"[{self.name}] n={n}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
