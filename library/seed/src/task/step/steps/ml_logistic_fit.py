"""L2-regularized logistic regression (numpy/scipy implementation)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import (
    accuracy, fit_logistic, label_vector, log_loss, matrix, predict_proba, roc_auc,
)


class MlLogisticFitStep(Step):
    """Fit a binary logistic model and report coefficients and fit metrics."""
    provider = 'operon-core'
    parameters_file = 'ml_logistic_fit.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_logistic_fit',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_logistic_fit',
        'description': 'Binary logistic regression with L2 penalty and fit diagnostics.',
        'category': 'Machine Learning',
        'icon': 'TrendingUp',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'feature_dim', 'default': 'feature'}],
                 'labels': []},
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'label_dim', 'default': 'label'}],
                 'labels': []},
            ],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'data', np.zeros(0)).nbytes) for item in inputs or [])
        return max(size * 6, 16 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = 'ml_logistic_fit'
        X = matrix(inputs[0], operator)
        y = label_vector(inputs[1], params.get('label_dim', 'label'), operator)
        if X.shape[0] != y.size:
            raise StepError(f'{operator}: feature rows do not match labels')
        binary = (y == np.max(y)).astype(np.int64)
        standardized = bool(params.get('standardize', False))
        if standardized:
            spread = X.std(axis=0)
            X = (X - X.mean(axis=0)) / np.where(spread == 0, 1.0, spread)
        coef, intercept, n_iter = fit_logistic(
            X, binary, C=float(params.get('C', 1.0)),
            fit_intercept=bool(params.get('fit_intercept', True)),
            max_iter=int(params.get('max_iter', 1000)),
        )
        proba = predict_proba(X, coef, intercept)
        feature_dim = params.get('feature_dim', 'feature')
        feature_labels = inputs[0].labels.get(feature_dim, {})
        if len(feature_labels) != X.shape[1]:
            feature_labels = {f'f{i}': i for i in range(X.shape[1])}
        data = np.column_stack([coef, np.exp(coef)])
        out = Form(
            data,
            dims=[feature_dim, 'statistic'],
            labels={feature_dim: dict(feature_labels),
                    'statistic': {'coef': 0, 'odds_ratio': 1}},
            info={'intercept': intercept, 'accuracy': accuracy(y, proba),
                  'roc_auc': roc_auc(y, proba), 'log_loss': log_loss(binary, proba),
                  'n_iter': n_iter, 'C': float(params.get('C', 1.0))},
        )
        out.validate()
        self._export_data = {
            'n_samples': int(y.size),
            'n_features': int(X.shape[1]),
            'intercept': float(intercept),
            'accuracy': float(accuracy(y, proba)),
            'roc_auc': float(roc_auc(y, proba)),
            'log_loss': float(log_loss(binary, proba)),
            'n_iter': int(n_iter),
        }
        ctx[params.get('output', 'coefficients')] = out

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
