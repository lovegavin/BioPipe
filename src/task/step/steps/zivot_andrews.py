"""Zivot-Andrews unit-root test with one structural break."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._entropy69_common import numeric_series
from ._stats20_common import scalar_form


class ZivotAndrewsStep(Step):
    name = "zivot_andrews"
    title = "Zivot-Andrews structural break unit-root test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
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
            "value_label": {"type": "string"},
            "regression": {"type": "string", "enum": ["c", "t", "ct"], "default": "c"},
            "trim": {"type": "number", "minimum": 0.01, "maximum": 0.33, "default": 0.15},
            "lags": {"type": ["integer", "null"], "minimum": 0, "default": None},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.stattools import zivot_andrews

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        regression = ctx.step_params.get("regression", "c")
        trim = float(ctx.step_params.get("trim", 0.15))
        lags = ctx.step_params.get("lags")
        out_name = ctx.step_params.get("output", self.name)

        values = numeric_series(inputs[0], sample_dim, feature_dim, value_label, self.name)
        n = int(values.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 finite values")
        maxlag = None if lags is None else int(lags)
        if maxlag is not None and maxlag >= n - 2:
            raise StepError(f"{self.name}: lags must be less than n - 2")
        try:
            statistic, pvalue, critical, baselag, bpidx = zivot_andrews(
                values,
                trim=trim,
                maxlag=maxlag,
                regression=regression,
                autolag="AIC" if maxlag is None else None,
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: Zivot-Andrews computation failed: {exc}") from exc

        keys = ["1%", "5%", "10%"]
        values_out = [
            float(statistic),
            float(pvalue),
            float(int(bpidx)),
            float(int(baselag)),
            float(n),
        ]
        values_out.extend(float(critical.get(key, np.nan)) for key in keys)
        out = scalar_form(
            values_out,
            ["statistic", "p", "break_index", "lag", "n", "critical_1pct", "critical_5pct", "critical_10pct"],
            "zivot_andrews",
        )
        out.info.update({
            "regression": regression,
            "trim": trim,
            "break_index_basis": "zero-based",
            "critical_values": "statsmodels table",
        })
        ctx[out_name] = out
        self._export_data = {
            "statistic": float(statistic),
            "p": float(pvalue),
            "break_index": int(bpidx),
            "lag": int(baselag),
            "n": n,
            "critical_1pct": float(critical.get("1%", np.nan)),
            "critical_5pct": float(critical.get("5%", np.nan)),
            "critical_10pct": float(critical.get("10%", np.nan)),
            "regression": regression,
            "trim": trim,
        }
        print(f"[zivot_andrews] statistic={float(statistic):.6f}, p={float(pvalue):.6g}, break={int(bpidx)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
