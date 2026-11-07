"""Robust Huber regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class HuberRegressorStep(_RegressionBase):
    provider = 'operon-core'
    parameters_file = 'huber_regressor.HuberRegressorStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'huber_regressor',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Huber regressor',
     'category': 'Machine Learning',
     'icon': 'Brain',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'label_dim', 'default': 'label'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['scikit-learn>=1.5'],
     'dependency_imports': ['sklearn'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Huber regressor：接收 2 个输入，输出 Form；主要参数：样本维度、特征维度、标签维度、目标字段、测试集比例、交叉验证折数。'}

    def _build_model(self, params, random_state):
        from sklearn.linear_model import HuberRegressor
        return HuberRegressor(
            epsilon=float(params.get("epsilon", 1.35)),
            alpha=float(params.get("alpha", 1e-4)),
            max_iter=int(params.get("max_iter", 100)),
        )
