"""Engle-Granger residual cointegration test for two series."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._cointegration_common import pair_series


class EngleGrangerStep(Step):
    name = "engle_granger"
    title = "Engle-Granger cointegration test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
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
            "y_label": {"type": "string"},
            "x_label": {"type": "string"},
            "trend": {"type": "string", "enum": ["c", "ct", "ctt"], "default": "c"},
            "lags": {"type": ["integer", "null"], "minimum": 0, "default": None},
            "output": {"type": "string"},
        },
        "required": ["y_label", "x_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.stattools import coint

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        y_label = ctx.step_params["y_label"]
        x_label = ctx.step_params["x_label"]
        trend = ctx.step_params.get("trend", "c")
        lags = ctx.step_params.get("lags")
        out_name = ctx.step_params.get("output", self.name)

        y, x, n = pair_series(inputs[0], sample_dim, feature_dim, y_label, x_label, self.name)
        maxlag = None if lags is None else int(lags)
        autolag = "aic" if lags is None else None
        if maxlag is not None and maxlag >= n - 2:
            raise StepError(f"{self.name}: lags must be less than n - 2")

        try:
            statistic, pvalue, critical = coint(
                y, x, trend=trend, maxlag=maxlag, autolag=autolag
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: cointegration computation failed: {exc}") from exc

        critical = np.asarray(critical, dtype=np.float64).ravel()
        if critical.size != 3 or not np.isfinite(critical).all():
            raise StepError(f"{self.name}: invalid critical values")
        rows = [
            ("statistic", float(statistic)),
            ("p", float(pvalue)),
            ("n", float(n)),
            ("critical_1pct", float(critical[0])),
            ("critical_5pct", float(critical[1])),
            ("critical_10pct", float(critical[2])),
        ]
        names = [name for name, _ in rows]
        form = Form(
            np.asarray([[value] for _, value in rows], dtype=np.float64),
            ["statistic", "value"],
            {"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
            {
                "missing_code": np.nan,
                "method": "Engle-Granger",
                "trend": trend,
                "lags": maxlag,
                "autolag": autolag,
                "variables": [y_label, x_label],
                "n": n,
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export = {
            "statistic": float(statistic),
            "p": float(pvalue),
            "n": n,
            "critical": {
                "1%": float(critical[0]),
                "5%": float(critical[1]),
                "10%": float(critical[2]),
            },
            "variables": [y_label, x_label],
            "trend": trend,
            "lags": maxlag,
        }
        print(f"[{self.name}] statistic={float(statistic):.4f}, p={float(pvalue):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
