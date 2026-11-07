"""Partial least-squares regression."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.cross_decomposition import PLSRegression

from ._ml_common import _RegressionBase


class _PlsRegressor(BaseEstimator, RegressorMixin):
    """PLSRegression adapter exposing a 1-D ``coef_`` for _MLBase.

    sklearn's PLSRegression stores ``coef_`` with shape
    ``(n_features, n_targets)`` for a single target.  The shared ML
    operator contract expects a one-dimensional coefficient vector, so
    this adapter flattens it after fitting while delegating prediction
    to the fitted estimator.
    """

    def __init__(self, n_components=2, max_iter=500, tol=1e-6):
        self.n_components = n_components
        self.max_iter = max_iter
        self.tol = tol

    def fit(self, X, y):
        self._model = PLSRegression(
            n_components=int(self.n_components),
            max_iter=int(self.max_iter),
            tol=float(self.tol),
            scale=False,
        )
        self._model.fit(X, y)
        self.coef_ = np.ravel(np.asarray(self._model.coef_, dtype=np.float64))
        return self

    def predict(self, X):
        return np.asarray(self._model.predict(X)).reshape(-1)


class PlsRegressionStep(_RegressionBase):
    provider = 'operon-core'
    parameters_file = 'pls_regression.PlsRegressionStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'pls_regression',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'PLS regression',
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
     'description': 'PLS regression：接收 2 个输入，输出 Form；主要参数：样本维度、特征维度、标签维度、目标字段、测试集比例、交叉验证折数。'}

    def _build_model(self, params, random_state):
        return _PlsRegressor(
            n_components=int(params.get("n_components", 2)),
            max_iter=int(params.get("max_iter", 500)),
            tol=float(params.get("tol", 1e-6)),
        )
