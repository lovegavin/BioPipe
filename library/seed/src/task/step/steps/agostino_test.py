"""D'Agostino skewness test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class AgostinoTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'agostino_test.AgostinoTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'agostino_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': "D'Agostino skewness test",
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
        'description': "D'Agostino's skewness test with a normal approximation "
                       "of the sample skewness.",
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        frame = table_frame(form, sample_dim, feature_dim, "agostino_test")
        values = numeric_column(frame, value_label, "agostino_test")
        values = np.sort(values[np.isfinite(values)])
        n = int(values.size)
        if n < 8 or n > 46340:
            raise StepError("agostino_test: sample size must be between 8 and 46340")
        centered = values - float(values.mean())
        m2 = float(np.mean(centered ** 2))
        if not m2 > 0.0:
            raise StepError("agostino_test: values are constant")
        skewness = float(np.mean(centered ** 3) / m2 ** 1.5)
        yn = skewness * np.sqrt((n + 1.0) * (n + 3.0) / (6.0 * (n - 2.0)))
        beta2 = 3.0 * (n * n + 27.0 * n - 70.0) * (n + 1.0) * (n + 3.0) / (
            (n - 2.0) * (n + 5.0) * (n + 7.0) * (n + 9.0))
        w2 = -1.0 + np.sqrt(2.0 * (beta2 - 1.0))
        if w2 <= 0.0:
            raise StepError("agostino_test: skewness statistic is undefined")
        w = np.sqrt(w2)
        delta = 1.0 / np.sqrt(np.log(w))
        alpha = np.sqrt(2.0 / (w * w - 1.0))
        z = delta * np.log(yn / alpha + np.sqrt((yn / alpha) ** 2 + 1.0))
        z = float(z)
        upper = float(stats.norm.sf(z))
        if alternative == "less":
            p_value = upper
        elif alternative == "greater":
            p_value = 1.0 - upper
        else:
            p_value = min(1.0, 2.0 * min(upper, 1.0 - upper))
        ctx[ctx.step_params.get("output", self.name)] = make_form(
            np.asarray([[skewness, z, p_value, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"agostino": 0},
             "value": {"skewness": 0, "z": 1, "p_value": 2, "n": 3}},
            {"method": "agostino_test"},
        )
        self._export = {"skewness": skewness, "statistic": z,
                        "p_value": float(p_value), "n": n}
        print(f"[agostino_test] skew={skewness:.6g} z={z:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
