"""Box-Pierce autocorrelation test for a univariate series."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BoxPierceStep(Step):
    name = "box_pierce"
    title = "Box-Pierce autocorrelation test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
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
            "fitdf": {"type": "integer", "minimum": 0, "default": 0},
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
        fitdf = int(ctx.step_params.get("fitdf", 0))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if lags < 1:
            raise StepError("box_pierce: lags must be at least 1")
        if fitdf < 0 or fitdf >= lags:
            raise StepError("box_pierce: fitdf must be >= 0 and < lags")
        if lags >= n:
            raise StepError("box_pierce: lags must be less than n")
        centered = values - values.mean()
        denom = float(np.sum(centered * centered))
        if denom <= 0:
            raise StepError("box_pierce: series has no variation")
        rho = []
        for lag in range(1, lags + 1):
            rho.append(float(np.sum(centered[lag:] * centered[:-lag]) / denom))
        q = float(n * np.sum(np.square(rho)))
        df = lags - fitdf
        p = float(stats.chi2.sf(q, df))
        ctx[out_name] = scalar_form(
            [q, float(df), p, float(n), float(lags), float(fitdf)],
            ["Q", "df", "p", "n", "lags", "fitdf"],
            "box_pierce",
        )
        self._export = {"Q": q, "df": df, "p": p, "n": n, "lags": lags, "fitdf": fitdf}
        print(f"[{self.name}] Q={q:.4f}, df={df}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
