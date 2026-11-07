"""Jarque-Bera normality test for every feature."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class JarqueBeraStep(Step):
    provider = 'operon-core'
    parameters_file = 'jarque_bera.JarqueBeraStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'jarque_bera',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Jarque-Bera normality test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
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
     'description': 'Jarque-Bera normality test：接收 1 个输入，输出 Form；主要参数：特征维度、样本维度。'}

    def run(self, ctx: Context, inputs) -> None:
        data = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        X, samples, features = matrix(data, sample_dim, feature_dim)
        rows = []
        for i in range(len(features)):
            res = stats.jarque_bera(X[:, i])
            rows.append([float(res.statistic), float(res.pvalue)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"JB": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "method": "jarque_bera"}
        print(f"[jarque_bera] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
