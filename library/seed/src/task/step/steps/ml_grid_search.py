"""Exhaustive grid search over regularization strength."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import label_vector, matrix
from src.task.step.steps._ml_validation import grid_search


class MlGridSearchStep(Step):
    provider = 'operon-core'
    parameters_file = 'ml_grid_search.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_grid_search',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_grid_search',
        'description': 'Exhaustive cross-validated search over logistic-regression C values.',
        'category': 'Machine Learning',
        'icon': 'Search',
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
        return max(size * 8, 16 * 1024 ** 2), 2 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        op = 'ml_grid_search'
        X = matrix(inputs[0], op)
        labels = label_vector(inputs[1], params.get('label_dim', 'label'), op)
        if X.shape[0] != labels.size:
            raise StepError(f'{op}: feature rows and labels differ')
        y = (labels == labels.max()).astype(int)
        values = [float(v) for v in str(params.get('C_values', '0.001,0.01,0.1,1,10')).split(',') if v.strip()]
        if not values:
            raise StepError(f'{op}: C_values is empty')
        rows, best = grid_search(
            X, y, values, int(params.get('n_splits', 5)), int(params.get('seed', 0)),
            bool(params.get('standardize', True)), str(params.get('metric', 'accuracy')))
        data = np.array(rows, dtype=float)
        out = Form(
            data, dims=['candidate', 'statistic'],
            labels={'candidate': {f'{r[0]:g}': i for i, r in enumerate(rows)},
                    'statistic': {'C': 0, 'mean_score': 1, 'std_score': 2}},
            info={'best_C': best, 'n_splits': int(params.get('n_splits', 5)),
                  'metric': params.get('metric', 'accuracy')},
        )
        out.validate()
        ctx[params.get('output', 'output')] = out
        self._export_data = {'best_C': best, 'n_candidates': len(rows),
                             'best_score': float(max(r[1] for r in rows))}

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
