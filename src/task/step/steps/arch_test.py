"""ARCH Lagrange-multiplier test for conditional heteroskedasticity."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.diagnostic import het_arch

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


_NAMES = ["lm_statistic", "lm_p", "f_statistic", "f_p", "lags", "n"]


class ArchTestStep(Step):
    name = "arch_test"
    title = "ARCH heteroskedasticity test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("time_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "time_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string"},
            "lags": {"type": "integer", "minimum": 1, "default": 5},
            "demean": {"type": "boolean", "default": False},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        time_dim = ctx.step_params.get("time_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = int(ctx.step_params.get("lags", 5))
        demean = bool(ctx.step_params.get("demean", False))
        if lags < 1:
            raise StepError("arch_test: lags must be at least 1")

        frame = table_frame(form, time_dim, feature_dim, "arch_test")
        if value_label not in frame.columns:
            raise StepError(f"arch_test: column {value_label!r} not found")
        values = numeric_column(frame, value_label, "arch_test")
        values = values[np.isfinite(values)]
        if values.size < lags + 2:
            raise StepError("arch_test: not enough complete observations")
        if np.var(values) == 0:
            raise StepError("arch_test: series is constant")
        if demean:
            values = values - float(np.mean(values))

        lm_stat, lm_p, f_stat, f_p = het_arch(values, nlags=lags)
        out_rows = [lm_stat, lm_p, f_stat, f_p, float(lags), float(values.size)]
        ctx[ctx.step_params.get("output", self.name)] = scalar_form(out_rows, _NAMES, "arch_test")
        self._export = {
            "lm_statistic": float(lm_stat),
            "lm_p": float(lm_p),
            "f_statistic": float(f_stat),
            "f_p": float(f_p),
            "lags": lags,
            "n": int(values.size),
            "demean": demean,
        }
        print(f"[arch_test] LM={lm_stat:.6g} p={lm_p:.6g}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return self._export
