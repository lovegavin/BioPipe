"""Stratified train/test split (sklearn-compatible)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_utils import label_vector, stratified_split


class MlTrainTestSplitStep(Step):
    """Split samples into train (0) and test (1) partitions."""
    provider = 'operon-core'
    parameters_file = 'ml_train_test_split.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ml_train_test_split',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ml_train_test_split',
        'description': 'Stratified train/test split with a reproducible seed.',
        'category': 'Machine Learning',
        'icon': 'Scissors',
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
        operator = 'ml_train_test_split'
        labels = label_vector(labels_form, params.get('label_dim', 'label'), operator)
        fraction = float(params.get('test_fraction', 0.25))
        if not 0.0 < fraction < 1.0:
            raise StepError(f'{operator}: test_fraction must be between 0 and 1')
        mask = stratified_split(labels, fraction, int(params.get('seed', 0)))
        sample_dim = params.get('sample_dim', 'sample')
        out = Form(
            mask.astype(np.int64).reshape(-1, 1),
            dims=[sample_dim, 'statistic'],
            labels={sample_dim: dict(labels_form.labels[sample_dim]),
                    'statistic': {'split': 0}},
            info={'test_fraction': fraction, 'seed': int(params.get('seed', 0)),
                  'n_train': int(np.sum(~mask)), 'n_test': int(np.sum(mask))},
        )
        out.validate()
        self._export_data = {
            'n_samples': int(labels.size),
            'n_train': int(np.sum(~mask)),
            'n_test': int(np.sum(mask)),
            'test_fraction': fraction,
        }
        ctx[params.get('output', 'split')] = out

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
