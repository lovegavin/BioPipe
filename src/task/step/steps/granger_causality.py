"""Granger causality tests on an ordered bivariate time-series table."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


_STATS = ["F", "p", "df_denom", "df_num"]


class GrangerCausalityStep(Step):
    name = "granger_causality"
    title = "Granger causality test"
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
            "cause_label": {"type": "string"},
            "effect_label": {"type": "string"},
            "max_lag": {"type": "integer", "minimum": 1, "default": 2},
            "output": {"type": "string"},
        },
        "required": ["cause_label", "effect_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        time_dim = ctx.step_params.get("time_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        cause_label = ctx.step_params["cause_label"]
        effect_label = ctx.step_params["effect_label"]
        max_lag = int(ctx.step_params.get("max_lag", 2))
        if max_lag < 1:
            raise StepError("granger_causality: max_lag must be at least 1")

        frame = table_frame(form, time_dim, feature_dim, "granger_causality")
        for name in (cause_label, effect_label):
            if name not in frame.columns:
                raise StepError(f"granger_causality: column {name!r} not found")
        cause = numeric_column(frame, cause_label, "granger_causality")
        effect = numeric_column(frame, effect_label, "granger_causality")
        valid = np.isfinite(cause) & np.isfinite(effect)
        cause = cause[valid]
        effect = effect[valid]
        if cause.size < max_lag + 3:
            raise StepError("granger_causality: not enough complete observations for max_lag")
        if np.var(cause) == 0 or np.var(effect) == 0:
            raise StepError("granger_causality: both series must vary")

        data = np.column_stack([effect, cause])
        with redirect_stdout(io.StringIO()):
            results = grangercausalitytests(data, maxlag=max_lag)
        rows = []
        for lag in range(1, max_lag + 1):
            f_stat, p_value, df_denom, df_num = results[lag][0]["ssr_ftest"]
            rows.append([float(f_stat), float(p_value), float(df_denom), float(df_num)])
        labels = {
            "lag": {str(lag): lag - 1 for lag in range(1, max_lag + 1)},
            "statistic": {name: i for i, name in enumerate(_STATS)},
        }
        out = make_form(
            np.asarray(rows, dtype=np.float64),
            ["lag", "statistic"],
            labels,
            {"method": "Granger causality (SSR F-test)", "cause": cause_label,
             "effect": effect_label, "max_lag": max_lag, "n": int(cause.size)},
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "cause": cause_label,
            "effect": effect_label,
            "max_lag": max_lag,
            "n": int(cause.size),
            "F": [row[0] for row in rows],
            "p": [row[1] for row in rows],
        }
        print(f"[granger_causality] {cause_label} -> {effect_label}, lags={max_lag}")

    def export(self, ctx: Context) -> dict:
        return self._export
