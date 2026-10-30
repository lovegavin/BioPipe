"""Cox-model IPCW Brier score at one or more times."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import port
from src.task.context import Context
from src.task.step.base import Step

from ._survival21_common import cox_brier, fit_cox, survival_columns


class BrierScoreStep(Step):
    """Cox PH Brier score with inverse-probability-of-censoring weights."""

    name = "brier_score"
    title = "Brier score (Cox)"
    category = "Survival"
    builtin_package = "biopipe-core"
    dependencies = ["lifelines>=0.30,<0.31", "pandas>=2"]
    dependency_imports = ["lifelines", "pandas"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2)]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "time_label": {"type": "string"},
            "event_label": {"type": "string"},
            "risk_label": {"type": "string"},
            "times": {"type": "array", "items": {"type": "number", "exclusiveMinimum": 0}, "minItems": 1},
            "output": {"type": "string"},
        },
        "required": ["time_label", "event_label", "risk_label", "times"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        times, events, risk = survival_columns(
            form, sample_dim, feature_dim,
            ctx.step_params["time_label"], ctx.step_params["event_label"],
            ctx.step_params["risk_label"],
        )
        eval_times = np.asarray(ctx.step_params["times"], dtype=float)
        cph, df = fit_cox(times, events, risk)
        brier = cox_brier(cph, df, times, events, risk, eval_times)
        values = np.column_stack([
            brier,
            np.full(eval_times.size, float(times.size)),
            np.full(eval_times.size, float(events.sum())),
        ])
        labels = {"time": {_time_label(t): i for i, t in enumerate(eval_times)},
                  "statistic": {"brier": 0, "n": 1, "events": 2}}
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=values.astype(np.float32),
            dims=["time", "statistic"],
            labels=labels,
            info={"missing_code": np.nan, "model": "coxph", "weighting": "ipcw"},
        )
        self._export_data = {
            "brier": [float(x) for x in brier],
            "times": [float(x) for x in eval_times],
            "coef": float(cph.params_.iloc[0]),
            "concordance": float(cph.concordance_index_),
            "n": int(times.size),
            "events": int(events.sum()),
        }
        print(
            f"[brier_score] times={eval_times.tolist()} brier={np.round(brier, 6).tolist()} "
            f"coef={float(cph.params_.iloc[0]):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _time_label(t: float) -> str:
    return f"{t:.10g}"
