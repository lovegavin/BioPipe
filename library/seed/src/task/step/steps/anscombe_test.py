"""Anscombe-Glynn kurtosis test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class AnscombeTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'anscombe_test.AnscombeTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'anscombe_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Anscombe-Glynn kurtosis test',
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
        'description': 'Anscombe-Glynn kurtosis test using the normal '
                       'approximation of the sample kurtosis.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        frame = table_frame(form, sample_dim, feature_dim, "anscombe_test")
        values = numeric_column(frame, value_label, "anscombe_test")
        values = np.sort(values[np.isfinite(values)])
        n = int(values.size)
        if n < 8 or n > 46340:
            raise StepError("anscombe_test: sample size must be between 8 and 46340")
        centered = values - float(values.mean())
        s2 = float(np.sum(centered ** 2))
        if not s2 > 0.0:
            raise StepError("anscombe_test: values are constant")
        kurtosis = float(n * np.sum(centered ** 4) / (s2 ** 2))
        expected = 3.0 * (n - 1.0) / (n + 1.0)
        varb2 = 24.0 * n * (n - 2.0) * (n - 3.0) / (
            (n + 1.0) ** 2 * (n + 3.0) * (n + 5.0))
        m3 = (6.0 * (n * n - 5.0 * n + 2.0) / ((n + 7.0) * (n + 9.0))) * np.sqrt(
            6.0 * (n + 3.0) * (n + 5.0) / (n * (n - 2.0) * (n - 3.0)))
        a = 6.0 + (8.0 / m3) * (2.0 / m3 + np.sqrt(1.0 + 4.0 / m3 ** 2))
        xx = (kurtosis - expected) / np.sqrt(varb2)
        z = (1.0 - 2.0 / (9.0 * a)
             - ((1.0 - 2.0 / a) / (1.0 + xx * np.sqrt(2.0 / (a - 4.0)))) ** (1.0 / 3.0)) / np.sqrt(
            2.0 / (9.0 * a))
        z = float(z)
        upper = float(stats.norm.sf(z))
        if alternative == "less":
            p_value = upper
        elif alternative == "greater":
            p_value = 1.0 - upper
        else:
            p_value = min(1.0, 2.0 * min(upper, 1.0 - upper))
        ctx[ctx.step_params.get("output", self.name)] = make_form(
            np.asarray([[kurtosis, z, p_value, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"anscombe": 0},
             "value": {"kurtosis": 0, "z": 1, "p_value": 2, "n": 3}},
            {"method": "anscombe_test"},
        )
        self._export = {"kurtosis": kurtosis, "statistic": z,
                        "p_value": float(p_value), "n": n}
        print(f"[anscombe_test] kurt={kurtosis:.6g} z={z:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
