"""Drop-one feature ablation for a fitted logistic model."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import (
    accuracy, fit_logistic, label_vector, log_loss, matrix, predict_proba, roc_auc,
)


class MlFeatureAblationStep(Step):
    """Change in AUC or accuracy when each feature is removed and refit."""
    provider = 'operon-core'
    parameters_file = 'ml_feature_ablation.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_feature_ablation',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_feature_ablation',
        'description': 'Drop-one feature importance by refitting the logistic model.',
        'category': 'Machine Learning',
        'icon': 'Filter',
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
        return max(size * 8, 32 * 1024 ** 2), 8 * 1024 ** 2

    def _score(self, X, y, binary, params):
        coef, intercept, _ = fit_logistic(
            X, binary, C=float(params.get('C', 1.0)),
            fit_intercept=bool(params.get('fit_intercept', True)),
            max_iter=int(params.get('max_iter', 1000)),
        )
        proba = predict_proba(X, coef, intercept)
        metric = params.get('metric', 'roc_auc')
        if metric == 'accuracy':
            return accuracy(y, proba)
        if metric == 'log_loss':
            return log_loss(binary, proba)
        if metric == 'roc_auc':
            return roc_auc(y, proba)
        raise StepError("metric must be 'roc_auc', 'accuracy' or 'log_loss'")

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = 'ml_feature_ablation'
        X = matrix(inputs[0], operator)
        y = label_vector(inputs[1], params.get('label_dim', 'label'), operator)
        if X.shape[0] != y.size:
            raise StepError(f'{operator}: feature rows do not match labels')
        if X.shape[1] < 2:
            raise StepError(f'{operator}: need at least two features')
        binary = (y == np.max(y)).astype(np.int64)
        standardized = bool(params.get('standardize', False))
        if standardized:
            spread = X.std(axis=0)
            X = (X - X.mean(axis=0)) / np.where(spread == 0, 1.0, spread)
        baseline = self._score(X, y, binary, params)
        deltas = np.zeros(X.shape[1], dtype=float)
        for index in range(X.shape[1]):
            keep = [j for j in range(X.shape[1]) if j != index]
            score = self._score(X[:, keep], y, binary, params)
            if params.get('metric', 'roc_auc') == 'log_loss':
                deltas[index] = score - baseline
            else:
                deltas[index] = baseline - score
        feature_dim = params.get('feature_dim', 'feature')
        feature_labels = inputs[0].labels.get(feature_dim, {})
        if len(feature_labels) != X.shape[1]:
            feature_labels = {f'f{i}': i for i in range(X.shape[1])}
        out = Form(
            deltas.reshape(-1, 1),
            dims=[feature_dim, 'statistic'],
            labels={feature_dim: dict(feature_labels), 'statistic': {'delta': 0}},
            info={'baseline': float(baseline), 'metric': params.get('metric', 'roc_auc')},
        )
        out.validate()
        self._export_data = {
            'n_features': int(X.shape[1]),
            'baseline': float(baseline),
            'metric': params.get('metric', 'roc_auc'),
            'most_important': feature_labels and max(
                feature_labels, key=lambda key: deltas[feature_labels[key]]),
        }
        ctx[params.get('output', 'importance')] = out

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
