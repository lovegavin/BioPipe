"""Stratified K-fold assignment (sklearn-compatible)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import label_vector, stratified_folds


class MlStratifiedFoldsStep(Step):
    """Assign samples to stratified folds."""
    provider = 'operon-core'
    parameters_file = 'ml_stratified_folds.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_stratified_folds',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_stratified_folds',
        'description': 'Stratified K-fold assignment with sklearn-compatible fold allocation.',
        'category': 'Machine Learning',
        'icon': 'Layers',
        'contracts': {
            'version': 1,
            'inputs': [
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
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], 'data', np.zeros(0)).nbytes) if inputs else 0
        return max(size * 4, 8 * 1024 ** 2), 2 * 1024 ** 2

    def run(self, ctx, inputs):
        labels_form = inputs[0]
        params = ctx.step_params
        operator = 'ml_stratified_folds'
        labels = label_vector(labels_form, params.get('label_dim', 'label'), operator)
        n_splits = int(params.get('n_splits', 5))
        if n_splits < 2:
            raise StepError(f'{operator}: n_splits must be at least 2')
        if n_splits > labels.size:
            raise StepError(f'{operator}: n_splits cannot exceed the sample count')
        folds = stratified_folds(labels, n_splits, bool(params.get('shuffle', True)),
                                 int(params.get('seed', 0)))
        sample_dim = params.get('sample_dim', 'sample')
        out = Form(
            folds.reshape(-1, 1),
            dims=[sample_dim, 'statistic'],
            labels={sample_dim: dict(labels_form.labels[sample_dim]),
                    'statistic': {'fold': 0}},
            info={'n_splits': n_splits, 'seed': int(params.get('seed', 0)),
                  'fold_sizes': [int(np.sum(folds == k)) for k in range(n_splits)]},
        )
        out.validate()
        self._export_data = {
            'n_samples': int(labels.size),
            'n_splits': n_splits,
            'fold_sizes': [int(np.sum(folds == k)) for k in range(n_splits)],
        }
        ctx[params.get('output', 'folds')] = out

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
