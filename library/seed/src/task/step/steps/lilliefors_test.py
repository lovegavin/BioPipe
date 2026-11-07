"""Lilliefors (Kolmogorov-Smirnov) normality test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class LillieforsTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'lilliefors_test.LillieforsTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'lilliefors_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Lilliefors normality test',
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
        'description': 'Lilliefors test for normality with estimated mean and '
                       'standard deviation, using the Kolmogorov-Smirnov statistic.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "lilliefors_test")
        values = numeric_column(frame, value_label, "lilliefors_test")
        values = np.sort(values[np.isfinite(values)])
        n = values.size
        if n < 5:
            raise StepError("lilliefors_test: sample size must be at least five")
        sd = float(values.std(ddof=1))
        if not sd > 0.0:
            raise StepError("lilliefors_test: values are constant")
        probabilities = stats.norm.cdf((values - float(values.mean())) / sd)
        ranks = np.arange(1, n + 1, dtype=np.float64)
        d_plus = float(np.max(ranks / n - probabilities))
        d_minus = float(np.max(probabilities - (ranks - 1.0) / n))
        statistic = max(d_plus, d_minus)
        if n <= 100:
            scaled, nd = statistic, n
        else:
            scaled = statistic * (n / 100.0) ** 0.49
            nd = 100
        p_value = float(np.exp(-7.01256 * scaled ** 2 * (nd + 2.78019)
                               + 2.99587 * scaled * np.sqrt(nd + 2.78019)
                               - 0.122119 + 0.974598 / np.sqrt(nd) + 1.67997 / nd))
        if p_value > 0.1:
            kk = (np.sqrt(n) - 0.01 + 0.85 / np.sqrt(n)) * statistic
            if kk <= 0.302:
                p_value = 1.0
            elif kk <= 0.5:
                p_value = (2.76773 - 19.828315 * kk + 80.709644 * kk ** 2
                           - 138.55152 * kk ** 3 + 81.218052 * kk ** 4)
            elif kk <= 0.9:
                p_value = (-4.901232 + 40.662806 * kk - 97.490286 * kk ** 2
                           + 94.029866 * kk ** 3 - 32.355711 * kk ** 4)
            elif kk <= 1.31:
                p_value = (6.198765 - 19.558097 * kk + 23.186922 * kk ** 2
                           - 12.234627 * kk ** 3 + 2.423045 * kk ** 4)
            else:
                p_value = 0.0
        p_value = float(min(1.0, max(0.0, p_value)))
        ctx[out_name] = make_form(
            np.asarray([[statistic, p_value, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"lilliefors": 0},
             "value": {"statistic": 0, "p_value": 1, "n": 2}},
            {"method": "lilliefors_test"},
        )
        self._export = {"statistic": statistic, "p_value": p_value, "n": n}
        print(f"[lilliefors_test] D={statistic:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
