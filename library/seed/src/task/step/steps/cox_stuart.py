"""Cox-Stuart test for a monotone trend."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class CoxStuartStep(Step):
    provider = 'operon-core'
    parameters_file = 'cox_stuart.CoxStuartStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'cox_stuart',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Cox-Stuart trend test',
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
        'description': 'Cox-Stuart sign test for a monotone trend by comparing '
                       'the first and second halves of a numeric series.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "cox_stuart")
        values = numeric_column(frame, value_label, "cox_stuart")
        values = values[np.isfinite(values)]
        size = values.size
        if size < 2:
            raise StepError("cox_stuart: need at least two finite observations")
        if size % 2 == 1:
            values = np.delete(values, (size - 1) // 2)
        half = values.size // 2
        first = values[:half]
        second = values[half:]
        pairs = np.count_nonzero(second - first != 0.0)
        statistic = int(np.count_nonzero(first < second))
        if pairs == 0:
            p_value = 1.0
        else:
            upper = float(stats.binom.cdf(statistic, pairs, 0.5))
            lower = float(1.0 - stats.binom.cdf(statistic - 1, pairs, 0.5))
            p_value = float(min(1.0, 2.0 * min(lower, upper)))
        ctx[out_name] = make_form(
            np.asarray([[statistic, pairs, p_value]], dtype=np.float64),
            ["test", "value"],
            {"test": {"cox_stuart": 0},
             "value": {"pairs_increasing": 0, "n_pairs": 1, "p_value": 2}},
            {"method": "cox_stuart", "alternative": "two.sided"},
        )
        self._export = {"statistic": statistic, "n_pairs": int(pairs), "p_value": p_value}
        print(f"[cox_stuart] increasing={statistic} pairs={pairs} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
