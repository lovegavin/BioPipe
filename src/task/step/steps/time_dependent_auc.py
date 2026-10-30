"""Time-dependent cumulative/dynamic AUC for a survival risk score."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import port
from src.task.context import Context
from src.task.step.base import Step


class TimeDependentAucStep(Step):
    """Kaplan-Meier cumulative/dynamic AUC at one prediction time."""

    name = "time_dependent_auc"
    title = "Time-dependent AUC"
    category = "Survival"
    builtin_package = "biopipe-core"
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
            "predict_time": {"type": "number", "exclusiveMinimum": 0},
            "output": {"type": "string"},
        },
        "required": ["time_label", "event_label", "risk_label", "predict_time"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        if form.data.ndim != 2:
            raise StepError("time_dependent_auc: input must be 2D")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        if sample_dim not in form.dims or feature_dim not in form.dims:
            raise StepError(
                f"time_dependent_auc: expected dims {sample_dim!r}, {feature_dim!r}, got {form.dims}"
            )
        labels = form.labels.get(feature_dim, {})
        for key in ("time_label", "event_label", "risk_label"):
            if ctx.step_params[key] not in labels:
                raise StepError(
                    f"time_dependent_auc: {ctx.step_params[key]!r} not in {sorted(labels)}"
                )
        predict_time = float(ctx.step_params["predict_time"])
        if not np.isfinite(predict_time) or predict_time <= 0:
            raise StepError("time_dependent_auc: predict_time must be finite and > 0")

        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(sample_dim) == 1:
            data = data.T
        times = data[:, labels[ctx.step_params["time_label"]]]
        events = data[:, labels[ctx.step_params["event_label"]]]
        risk = data[:, labels[ctx.step_params["risk_label"]]]
        keep = np.isfinite(times) & np.isfinite(events) & np.isfinite(risk)
        keep &= times > 0
        keep &= np.isin(events, (0, 1))
        times, events, risk = times[keep], events.astype(int)[keep], risk[keep]
        if times.size < 4:
            raise StepError("time_dependent_auc: fewer than four usable samples")
        if np.unique(risk).size < 2:
            raise StepError("time_dependent_auc: risk score must have at least two values")

        s_pool = _km_survival(times, events, predict_time)
        cases = int(np.sum((times <= predict_time) & (events == 1)))
        controls = int(np.sum(times > predict_time))
        if cases == 0 or controls == 0 or s_pool >= 1.0:
            raise StepError(
                "time_dependent_auc: predict_time must have both cases and controls"
            )

        cut_values = np.unique(risk)
        xs = [1.0]
        ys = [1.0]
        for cut in cut_values[:-1]:
            subset = risk > cut
            p0 = float(np.mean(subset))
            if p0 <= 0:
                sens = 0.0
                spec = 1.0
            else:
                s0 = _km_survival(times[subset], events[subset], predict_time)
                sens = (1.0 - s0) * p0 / (1.0 - s_pool)
                spec = 1.0 - s0 * p0 / s_pool
            xs.append(1.0 - spec)
            ys.append(sens)
        xs.append(0.0)
        ys.append(0.0)
        xs_arr = np.asarray(xs, dtype=np.float64)
        ys_arr = np.asarray(ys, dtype=np.float64)
        auc = float(np.sum((xs_arr[:-1] - xs_arr[1:]) * (ys_arr[:-1] + ys_arr[1:]) * 0.5))
        auc = min(1.0, max(0.0, auc))

        rows = [
            ["AUC", auc],
            ["predict_time", predict_time],
            ["n_cases", cases],
            ["n_controls", controls],
            ["n", int(times.size)],
        ]
        out = Form(
            data=np.asarray([[v] for _, v in rows], dtype=np.float32),
            dims=["metric", "value"],
            labels={"metric": {name: i for i, (name, _) in enumerate(rows)}, "value": {"value": 0}},
            info={"missing_code": np.nan, "method": "KM", "auc": auc},
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export_data = {
            "auc": auc,
            "predict_time": predict_time,
            "n": int(times.size),
            "n_cases": cases,
            "n_controls": controls,
            "method": "KM",
        }
        print(
            f"[time_dependent_auc] AUC={auc:.4f}, t={predict_time:g}, "
            f"cases={cases}, controls={controls}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _km_survival(times: np.ndarray, events: np.ndarray, t: float) -> float:
    """Kaplan-Meier survival at t; events are 1 for the event of interest."""
    survival = 1.0
    for at in np.unique(times[times <= t]):
        n = int(np.sum(times >= at))
        d = int(np.sum((times == at) & (events == 1)))
        if n > 0:
            survival *= 1.0 - d / n
    return float(survival)
