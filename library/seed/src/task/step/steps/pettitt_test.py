"""Pettitt change-point test for a single series."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class PettittTestStep(Step):
    provider = 'operon-core'
    """Pettitt's non-parametric single change-point test.

    The statistic is ``U = max_k |2 sum_{i<=k} rank(x_i) - k(n+1)|`` and the
    two-sided p-value is ``min(1, 2 exp(-6U^2/(n^3+n^2)))``, matching
    ``trend::pettitt.test``.
    """
    parameters_file = 'pettitt_test.PettittTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'pettitt_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Pettitt change-point test',
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
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Pettitt's non-parametric single change-point test."}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "pettitt_test")
        values = np.asarray(numeric_column(frame, value_label, "pettitt_test"), dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 2:
            raise StepError("pettitt_test: need at least two observations")
        ranks = stats.rankdata(values, method="average")
        positions = np.arange(1, n + 1, dtype=np.float64)
        uk = 2.0 * np.cumsum(ranks) - positions * (n + 1)
        absolute = np.abs(uk)
        statistic = float(absolute.max())
        points = [int(position) for position in positions[absolute == statistic]]
        exponent = -6.0 * statistic * statistic / (float(n) ** 3 + float(n) ** 2)
        p_value = min(1.0, 2.0 * math.exp(exponent))

        out = scalar_form(
            [statistic, p_value, float(points[0]), float(n)],
            ["U", "p", "change_point", "n"],
            "pettitt_test",
        )
        out.info.update({
            "change_points": points,
            "alternative": "two-sided",
            "method": "Pettitt",
        })
        ctx[out_name] = out
        self._export_data = {
            "U": statistic,
            "p": p_value,
            "change_point": points[0],
            "change_points": points,
            "n": n,
        }
        print(f"[pettitt_test] U={statistic:.6g}, p={p_value:.6g}, K={points[0]}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
