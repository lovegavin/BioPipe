"""Restricted mean survival time (RMST) from a clinical table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values, make_form


class RmstStep(Step):
    name = "rmst"
    title = "Restricted mean survival"
    category = "Survival"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "time_label": {"type": "string"},
            "event_label": {"type": "string"},
            "group_label": {"type": "string"},
            "tau": {"type": ["number", "null"], "exclusiveMinimum": 0, "default": None},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "required": ["time_label", "event_label"],
        "additionalProperties": False,
    }

    def _column(self, form, sample_dim, feature_dim, label):
        if label not in form.labels.get(feature_dim, {}):
            raise StepError(f"clinical column {label!r} not found")
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(np.asarray(form.data), axis, 0)
        return data[:, form.labels[feature_dim][label]].astype(np.float64)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        time_label = ctx.step_params["time_label"]
        event_label = ctx.step_params["event_label"]
        group_label = ctx.step_params.get("group_label")
        tau = ctx.step_params.get("tau")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        times = self._column(form, sample_dim, feature_dim, time_label)
        events = self._column(form, sample_dim, feature_dim, event_label)
        good = np.isfinite(times) & np.isfinite(events) & (times >= 0)
        if not good.any():
            raise StepError("rmst: no finite non-negative survival times")
        times, events = times[good], (events[good] > 0).astype(int)
        if group_label:
            _, groups = group_values(form, sample_dim, group_label)
            groups = np.asarray(groups)[good]
            group_names = sorted({str(g) for g in groups})
        else:
            groups = np.asarray(["all"] * len(times), dtype=object)
            group_names = ["all"]
        tau_value = float(tau) if tau is not None else float(np.max(times))
        if tau_value <= 0:
            raise StepError("rmst: tau must be positive")
        z = stats.norm.ppf(0.5 + confidence / 2.0)
        rows = []
        for g in group_names:
            mask = np.array([str(v) == g for v in groups])
            t = times[mask]; e = events[mask]
            if len(t) == 0:
                rows.append([np.nan, np.nan, np.nan, np.nan, 0, 0]); continue
            area, var, prev, surv = 0.0, 0.0, 0.0, 1.0
            for ev_t in np.unique(t[e == 1]):
                if ev_t > tau_value:
                    break
                area += surv * (ev_t - prev)
                n_risk = int(np.sum(t >= ev_t))
                d = int(np.sum((t == ev_t) & (e == 1)))
                if n_risk > 0 and n_risk > d:
                    var += (surv ** 2) * d / (n_risk * (n_risk - d)) * (tau_value - ev_t) ** 2
                    surv *= (1.0 - d / n_risk)
                elif n_risk > 0:
                    surv = 0.0
                prev = ev_t
            if tau_value > prev:
                area += surv * (tau_value - prev)
            se = float(np.sqrt(max(var, 0.0)))
            rows.append([float(area), se, float(area - z * se), float(area + z * se), int(len(t)), int(e.sum())])
        out = make_form(rows, ["group", "statistic"],
                        {"group": {name: i for i, name in enumerate(group_names)},
                         "statistic": {"rmst": 0, "se": 1, "ci_low": 2, "ci_high": 3, "n": 4, "n_events": 5}})
        ctx[out_name] = out
        self._export_data = {"tau": tau_value, "confidence": confidence,
                             "groups": group_names, "rmst": {g: float(rows[i][0]) for i, g in enumerate(group_names)}}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
