"""D'Agostino-Pearson normality test per feature.

Computes scipy.stats.normaltest independently for each feature. At
least eight samples are required by the test. Missing values are
mean-imputed by the shared matrix helper.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class NormaltestStep(Step):
    provider = 'operon-core'
    parameters_file = 'normaltest.NormaltestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'normaltest',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "D'Agostino-Pearson normality test",
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
     'description': "D'Agostino-Pearson normality test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度。"}

    def run(self, ctx: Context, inputs) -> None:
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        X, _samples, features = matrix(inputs[0], sample_dim, feature_dim)
        if X.shape[0] < 8:
            raise StepError("normaltest needs at least eight samples")
        rows = []
        for i in range(X.shape[1]):
            try:
                statistic, pvalue = stats.normaltest(X[:, i])
            except ValueError:
                statistic, pvalue = float("nan"), float("nan")
            rows.append([float(statistic), float(pvalue)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"K2": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export = {"n_features": len(features), "n_samples": int(X.shape[0]), "method": "normaltest"}
        print(f"[normaltest] {len(features)} features, {X.shape[0]} samples")

    def export(self, ctx: Context) -> dict:
        return self._export
