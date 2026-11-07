"""Cumulative incidence for competing risks (Aalen-Johansen)."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class CumulativeIncidenceStep(Step):
    provider = 'operon-core'
    parameters_file = 'cumulative_incidence.CumulativeIncidenceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cumulative_incidence',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Cumulative incidence',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Cumulative incidence：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、随访时间字段、事件字段、分组字段、Event Of '
                    'Interest。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        time_label = ctx.step_params["time_label"]
        event_label = ctx.step_params["event_label"]
        group_label = ctx.step_params.get("group_label")
        event_interest = int(ctx.step_params.get("event_of_interest", 1))
        event_competing = int(ctx.step_params.get("competing_event", 2))
        groups_arg = ctx.step_params.get("groups")
        horizon = ctx.step_params.get("horizon")
        out_name = ctx.step_params.get("output", self.name)
        if form.data.ndim != 2:
            raise StepError("cumulative_incidence: input must be 2D")
        for dim in (sample_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(f"cumulative_incidence: dim {dim!r} not in {form.dims}")
        if event_interest == event_competing:
            raise StepError("cumulative_incidence: event_of_interest and competing_event must differ")
        if 0 in (event_interest, event_competing):
            raise StepError("cumulative_incidence: event codes 1 and 2 must differ from censoring code 0")
        labels = form.labels.get(feature_dim, {})
        for name in (time_label, event_label):
            if name not in labels:
                raise StepError(f"cumulative_incidence: column {name!r} not found")
        if group_label is not None and group_label not in labels:
            raise StepError(f"cumulative_incidence: group column {group_label!r} not found")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(sample_dim) == 1:
            data = data.T
        times = data[:, labels[time_label]]
        events = data[:, labels[event_label]]
        if group_label is None:
            group_values = np.asarray(["all"] * data.shape[0], dtype=object)
        else:
            group_values = data[:, labels[group_label]]
            encoders = form.info.get("encoders", {})
            encoder = encoders.get(feature_dim, {}).get(group_label)
            if encoder is not None and hasattr(encoder, "inverse_transform"):
                group_values = encoder.inverse_transform(group_values.astype(np.int64))
        keep = np.isfinite(times) & np.isfinite(events)
        times, events, group_values = times[keep], events[keep], np.asarray(group_values)[keep]
        if times.size == 0:
            raise StepError("cumulative_incidence: no finite time/event rows")
        if np.any(times <= 0):
            raise StepError("cumulative_incidence: times must be > 0")
        event_codes = np.asarray(events, dtype=np.int64)
        if not np.allclose(events, event_codes):
            raise StepError("cumulative_incidence: event codes must be integers")
        allowed = {0, event_interest, event_competing}
        bad = sorted(set(event_codes.tolist()) - allowed)
        if bad:
            raise StepError(
                f"cumulative_incidence: event codes must be 0, {event_interest} or "
                f"{event_competing}; found {bad}"
            )
        if horizon is not None and float(horizon) <= 0:
            raise StepError("cumulative_incidence: horizon must be > 0")

        present = sorted({_group_key(v) for v in group_values})
        if groups_arg is not None:
            groups = [_group_key(g) for g in groups_arg]
            missing = [g for g in groups if g not in present]
            if missing:
                raise StepError(f"cumulative_incidence: groups not found: {missing}")
        else:
            groups = present
        if not groups:
            raise StepError("cumulative_incidence: no groups to summarize")

        curves: dict[str, list[tuple[float, float]]] = {}
        for group in groups:
            mask = np.asarray([_group_key(v) == group for v in group_values])
            t = times[mask]
            e = event_codes[mask]
            curve = _cif_curve(t, e, event_interest, event_competing)
            curves[group] = curve

        max_time = max((t for curve in curves.values() for t, _ in curve), default=0.0)
        if horizon is not None:
            max_time = min(max_time, float(horizon))
        all_times = sorted({0.0} | {t for curve in curves.values() for t, _ in curve if t <= max_time})
        rows = []
        for t in all_times:
            row = []
            for group in groups:
                value = 0.0
                for ct, cv in curves[group]:
                    if ct <= t:
                        value = cv
                    else:
                        break
                row.append(value)
            rows.append(row)

        out = make_form(
            np.asarray(rows, dtype=np.float64),
            ["time", "group"],
            {"time": {_time_label(t): i for i, t in enumerate(all_times)},
             "group": {group: i for i, group in enumerate(groups)}},
        )
        ctx[out_name] = out
        self._export_data = {
            "groups": groups,
            "event_of_interest": event_interest,
            "competing_event": event_competing,
            "n_samples": int(times.size),
            "n_times": len(all_times),
            "horizon": float(horizon) if horizon is not None else None,
        }
        print(
            f"[cumulative_incidence] groups={groups} samples={times.size} "
            f"times={len(all_times)}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _time_label(t: float) -> str:
    return f"{t:.10g}"


def _cif_curve(times, events, interest, competing):
    """Return (time, CIF) points for one group."""
    event_times = sorted({float(t) for t in times if t > 0})
    survival = 1.0
    cif = 0.0
    curve = [(0.0, 0.0)]
    for t in event_times:
        at_risk = int(np.sum(times >= t))
        if at_risk <= 0:
            break
        d1 = int(np.sum((times == t) & (events == interest)))
        d2 = int(np.sum((times == t) & (events == competing)))
        if d1 == 0 and d2 == 0:
            continue
        cif += survival * d1 / at_risk
        survival *= 1.0 - (d1 + d2) / at_risk
        curve.append((t, float(cif)))
    return curve


def _group_key(value) -> str:
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number)
    except (TypeError, ValueError):
        return str(value)
