"""Integrated Cox-model Brier score over a supplied time grid."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import port
from src.task.context import Context
from src.task.step.base import Step

from ._survival21_common import cox_brier, fit_cox, survival_columns


class IntegratedBrierScoreStep(Step):
    """Trapezoidal integral of the Cox IPCW Brier score."""

    name = "integrated_brier_score"
    title = "Integrated Brier score (Cox)"
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
            "times": {"type": "array", "items": {"type": "number", "exclusiveMinimum": 0}, "minItems": 2},
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
        if np.any(np.diff(eval_times) <= 0):
            raise StepError("integrated_brier_score: times must be strictly increasing")
        cph, df = fit_cox(times, events, risk)
        brier = cox_brier(cph, df, times, events, risk, eval_times)
        ibs = float(np.sum(np.diff(eval_times) * (brier[:-1] + brier[1:]) * 0.5))
        rows = [
            ["integrated_brier", ibs],
            ["time_min", float(eval_times[0])],
            ["time_max", float(eval_times[-1])],
            ["n_times", int(eval_times.size)],
            ["n", int(times.size)],
            ["events", int(events.sum())],
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[v] for _, v in rows], dtype=np.float32),
            dims=["metric", "value"],
            labels={"metric": {name: i for i, (name, _) in enumerate(rows)}, "value": {"value": 0}},
            info={"missing_code": np.nan, "model": "coxph", "weighting": "ipcw"},
        )
        self._export_data = {
            "integrated_brier": ibs,
            "times": [float(x) for x in eval_times],
            "brier": [float(x) for x in brier],
            "n": int(times.size),
            "events": int(events.sum()),
        }
        print(f"[integrated_brier_score] IBS={ibs:.6f}, times={len(eval_times)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
