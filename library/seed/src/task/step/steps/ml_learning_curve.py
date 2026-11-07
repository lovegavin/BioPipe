"""Cross-validated learning curve."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import label_vector, matrix
from src.task.step.steps._ml_validation import learning_curve


class MlLearningCurveStep(Step):
    provider = 'operon-core'
    parameters_file = 'ml_learning_curve.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_learning_curve',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_learning_curve',
        'description': 'Training and test scores as a function of training-set size, stratified K-fold.',
        'category': 'Machine Learning',
        'icon': 'TrendingUp',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'feature_dim', 'default': 'feature'}], 'labels': []},
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'label_dim', 'default': 'label'}], 'labels': []},
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
        size = int(getattr(inputs[0], 'data', np.zeros(0)).nbytes) if inputs else 0
        return max(size * 6, 16 * 1024 ** 2), 2 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        op = 'ml_learning_curve'
        X = matrix(inputs[0], op)
        labels = label_vector(inputs[1], params.get('label_dim', 'label'), op)
        if X.shape[0] != labels.size:
            raise StepError(f'{op}: feature rows and labels differ')
        y = (labels == labels.max()).astype(int)
        fractions = [float(v) for v in str(params.get('train_sizes', '0.2,0.4,0.6,0.8,1.0')).split(',') if v.strip()]
        if not fractions:
            raise StepError(f'{op}: train_sizes is empty')
        n_splits = int(params.get('n_splits', 5))
        rows = learning_curve(
            X, y, fractions, n_splits, int(params.get('seed', 0)),
            float(params.get('C', 1.0)), bool(params.get('standardize', True)),
            str(params.get('metric', 'accuracy')))
        data = np.array([[r[0], r[1], r[2], r[3], r[4]] for r in rows], dtype=float)
        sample_dim = params.get('sample_dim', 'sample')
        out = Form(
            data, dims=['size', 'statistic'],
            labels={'size': {f'{int(r[0])}': i for i, r in enumerate(rows)},
                    'statistic': {'n_train': 0, 'train_mean': 1, 'train_std': 2,
                                  'test_mean': 3, 'test_std': 4}},
            info={'n_splits': n_splits, 'metric': params.get('metric', 'accuracy'),
                  'n_samples': int(labels.size)},
        )
        out.validate()
        ctx[params.get('output', 'output')] = out
        self._export_data = {
            'n_sizes': len(rows), 'max_train_size': int(rows[-1][0]) if rows else 0,
            'best_test_mean': float(max(r[3] for r in rows)) if rows else 0.0,
        }

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
