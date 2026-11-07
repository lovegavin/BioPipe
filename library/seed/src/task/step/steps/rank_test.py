"""Mann-Kendall rank test for a monotone trend."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class RankTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'rank_test.RankTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rank_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Mann-Kendall rank test',
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
        'description': 'Mann-Kendall rank correlation test using the number of '
                       'later observations larger than each earlier observation.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "rank_test")
        values = numeric_column(frame, value_label, "rank_test")
        values = values[np.isfinite(values)]
        n = values.size
        if n < 2:
            raise StepError("rank_test: need at least two finite observations")
        pairs = 0
        for index in range(n - 1):
            pairs += int(np.count_nonzero(values[index + 1:] > values[index]))
        mean = n * (n - 1) / 4.0
        variance = n * (n - 1) * (2 * n + 5) / 72.0
        z = (pairs - mean) / np.sqrt(variance)
        p_value = float(2.0 * min(stats.norm.cdf(z), 1.0 - stats.norm.cdf(z)))
        ctx[out_name] = make_form(
            np.asarray([[z, pairs, mean, variance, p_value, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"rank_test": 0},
             "value": {"statistic": 0, "P": 1, "expected": 2, "variance": 3,
                       "p_value": 4, "n": 5}},
            {"method": "rank_test", "alternative": "two.sided"},
        )
        self._export = {"statistic": float(z), "P": pairs, "expected": mean,
                        "variance": variance, "p_value": p_value, "n": n}
        print(f"[rank_test] P={pairs} z={z:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
