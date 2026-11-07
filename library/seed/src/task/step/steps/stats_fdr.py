"""Multiple-testing correction (BH, BY, Holm, Bonferroni)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._ml_validation import bh_adjust


class StatsFdrStep(Step):
    provider = 'operon-core'
    parameters_file = 'stats_fdr.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'stats_fdr',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'stats_fdr',
        'description': 'Multiple-testing adjusted p-values and rejections (BH, BY, Holm, Bonferroni).',
        'category': 'Statistics',
        'icon': 'ListChecks',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'test_dim', 'default': 'test'},
                          {'param': 'pvalue_dim', 'default': 'pvalue'}],
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
        return 16 * 1024 ** 2, 2 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        op = 'stats_fdr'
        form = inputs[0]
        data = np.asarray(form.data, dtype=float)
        if data.ndim != 2 or data.shape[1] != 1:
            raise StepError(f'{op}: expected an (n, 1) p-value matrix')
        p = data[:, 0]
        if np.any(~np.isfinite(p)) or np.any(p < 0) or np.any(p > 1):
            raise StepError(f'{op}: p-values must be finite and within [0, 1]')
        method = str(params.get('method', 'bh')).lower()
        alpha = float(params.get('alpha', 0.05))
        adjusted = bh_adjust(p, method)
        rows = np.column_stack([p, adjusted, (adjusted <= alpha).astype(float)])
        test_dim = params.get('test_dim', 'test')
        out = Form(
            rows, dims=[test_dim, 'statistic'],
            labels={test_dim: dict(form.labels[test_dim]),
                    'statistic': {'p_value': 0, 'adjusted_p': 1, 'rejected': 2}},
            info={'method': method, 'alpha': alpha, 'n_tests': int(p.size),
                  'n_rejected': int(np.sum(adjusted <= alpha))},
        )
        out.validate()
        ctx[params.get('output', 'output')] = out
        self._export_data = {'method': method, 'n_tests': int(p.size),
                             'n_rejected': int(np.sum(adjusted <= alpha))}

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
