"""Shapiro-Wilk normality test for every feature."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class ShapiroStep(Step):
    provider = 'operon-core'
    parameters_file = 'shapiro.ShapiroStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'shapiro',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Shapiro-Wilk test',
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
     'description': 'Shapiro-Wilk test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, _samples, features = matrix(form, sample_dim, feature_dim)
        if X.shape[0] < 3:
            raise StepError("shapiro needs at least three samples per feature")
        rows = []
        for i in range(len(features)):
            w, p = stats.shapiro(X[:, i])
            rows.append([float(w), float(p)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)}, "statistic": {"W": 0, "P": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_samples": int(X.shape[0])}
        print(f"[shapiro] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
