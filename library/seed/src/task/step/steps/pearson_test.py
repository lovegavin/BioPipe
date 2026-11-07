"""Pearson chi-square test for normality."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class PearsonTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'pearson_test.PearsonTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'pearson_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Pearson chi-square normality test',
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
        'description': 'Pearson chi-square goodness-of-fit test for normality '
                       'with equiprobable classes and estimated mean and standard deviation.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        n_classes = ctx.step_params.get("n_classes")
        adjust = bool(ctx.step_params.get("adjust", True))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "pearson_test")
        values = numeric_column(frame, value_label, "pearson_test")
        values = values[np.isfinite(values)]
        n = values.size
        if n < 5:
            raise StepError("pearson_test: sample size must be at least five")
        sd = float(values.std(ddof=1))
        if not sd > 0.0:
            raise StepError("pearson_test: values are constant")
        classes = int(n_classes) if n_classes else int(math.ceil(2.0 * n ** 0.4))
        if classes < 2:
            raise StepError("pearson_test: n_classes must be at least two")
        probabilities = stats.norm.cdf(values, float(values.mean()), sd)
        counts = np.zeros(classes + 1, dtype=np.int64)
        index = np.floor(1.0 + classes * probabilities).astype(np.int64)
        for value in index:
            if 1 <= value <= classes:
                counts[value] += 1
        observed = counts[1:classes + 1].astype(np.float64)
        expected = n / classes
        statistic = float(np.sum((observed - expected) ** 2 / expected))
        degrees = classes - 1 - (2 if adjust else 0)
        if degrees < 1:
            raise StepError("pearson_test: n_classes is too small for the chosen adjustment")
        p_value = float(stats.chi2.sf(statistic, degrees))
        ctx[out_name] = make_form(
            np.asarray([[statistic, degrees, p_value, classes, n]], dtype=np.float64),
            ["test", "value"],
            {"test": {"pearson_test": 0},
             "value": {"statistic": 0, "df": 1, "p_value": 2, "n_classes": 3, "n": 4}},
            {"method": "pearson_test", "adjust": adjust},
        )
        self._export = {"statistic": statistic, "df": degrees, "p_value": p_value,
                        "n_classes": classes, "n": n}
        print(f"[pearson_test] X2={statistic:.6g} df={degrees} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
