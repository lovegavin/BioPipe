"""Nelson-Aalen cumulative hazard estimator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class NelsonAalenStep(Step):
    provider = 'operon-core'
    parameters_file = 'nelson_aalen.NelsonAalenStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'nelson_aalen',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Nelson-Aalen cumulative hazard',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': ('Nelson-Aalen：接收 1 个输入，按随访时间字段与事件字段计算累计风险、'
                     '风险集人数、事件数与标准误。')}

    def _column(self, form, sample_dim, feature_dim, label):
        if label not in form.labels.get(feature_dim, {}):
            raise StepError(f"nelson_aalen: clinical column {label!r} not found")
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(np.asarray(form.data), axis, 0)
        return np.asarray(data[:, form.labels[feature_dim][label]]).astype(np.float64)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        time_label = ctx.step_params["time_label"]
        event_label = ctx.step_params["event_label"]
        out_name = ctx.step_params.get("output", self.name)
        times = self._column(form, sample_dim, feature_dim, time_label)
        events = self._column(form, sample_dim, feature_dim, event_label)
        good = np.isfinite(times) & np.isfinite(events) & (times >= 0)
        if not good.any():
            raise StepError("nelson_aalen: no finite non-negative survival times")
        times = times[good]
        events = events[good] > 0
        if not events.any():
            raise StepError("nelson_aalen: no events observed")
        unique_times = np.unique(times)
        cumulative = 0.0
        variance = 0.0
        rows = []
        for value in unique_times:
            at_risk = int(np.sum(times >= value))
            observed = int(np.sum((times == value) & events))
            if observed:
                for j in range(observed):
                    cumulative += 1.0 / float(at_risk - j)
                    variance += 1.0 / float(at_risk - j) ** 2
            rows.append([float(at_risk), float(observed), float(cumulative),
                         float(np.sqrt(max(variance, 0.0)))])
        time_keys = []
        seen = {}
        for value in unique_times:
            key = f"{float(value):.12g}"
            if key in seen:
                seen[key] += 1
                key = f"{key}#{seen[key]}"
            else:
                seen[key] = 0
            time_keys.append(key)
        labels = {
            "time": {key: i for i, key in enumerate(time_keys)},
            "statistic": {"n_risk": 0, "n_event": 1, "cumhaz": 2, "se": 3},
        }
        ctx[out_name] = make_form(rows, ["time", "statistic"], labels)
        self._export_data = {
            "n": int(times.size),
            "n_events": int(events.sum()),
            "n_times": int(unique_times.size),
            "times": [float(v) for v in unique_times],
            "cumhaz": [float(row[2]) for row in rows],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
