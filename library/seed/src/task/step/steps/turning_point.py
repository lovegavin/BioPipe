"""Turning point test for serial randomness."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class TurningPointStep(Step):
    provider = 'operon-core'
    parameters_file = 'turning_point.TurningPointStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'turning_point',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Turning point test',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{'version': 1, 'numeric': True, 'info': {},
                        'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                 {'param': 'feature_dim', 'default': 'feature'}],
                        'labels': [], 'parallel': [], 'ndim': 2}],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
        'dependency_imports': ['numpy', 'scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Wald-Wolfowitz turning point test of serial randomness; '
                       'tied consecutive values are removed before counting.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "turning_point")
        values = numeric_column(frame, value_label, "turning_point")
        values = values[np.isfinite(values)]
        if values.size < 4:
            raise StepError("turning_point: fewer than four finite observations")
        # R randtests removes the earlier member of every consecutive tie.
        ties = np.flatnonzero(np.diff(values) == 0.0)
        if ties.size:
            values = np.delete(values, ties)
        n = values.size
        if n < 4:
            raise StepError("turning_point: too few distinct consecutive values")
        steps = np.diff(values)
        turning = int(np.count_nonzero(steps[:-1] * steps[1:] < 0.0))
        mean = 2.0 * (n - 2) / 3.0
        variance = (16.0 * n - 29.0) / 90.0
        z = (turning - mean) / np.sqrt(variance)
        p = float(2.0 * min(stats.norm.cdf(z), 1.0 - stats.norm.cdf(z)))
        ctx[out_name] = make_form(
            np.asarray([[z, turning, p, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"turning_point": 0},
             "value": {"statistic": 0, "turning_points": 1, "p_value": 2, "n": 3}},
            {"method": "turning_point"},
        )
        self._export = {"statistic": float(z), "turning_points": turning,
                        "p_value": p, "n": n}
        print(f"[turning_point] z={z:.6g} points={turning} p={p:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
