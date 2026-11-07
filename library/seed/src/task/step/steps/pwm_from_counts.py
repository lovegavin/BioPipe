"""Build a position weight matrix from a position frequency matrix."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from src.task.step.steps._pwm_utils import (
    BASES,
    best_base,
    counts_matrix,
    information_content,
    parse_background,
    pwm_matrix,
)


class PwmFromCountsStep(Step):
    """Convert a PFM (counts per position and base) into a log-odds PWM."""

    provider = 'operon-core'
    parameters_file = 'pwm_from_counts.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'pwm_from_counts',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'pwm_from_counts',
        'description': 'Build a log-odds PWM and information content from a PFM.',
        'category': 'Sequence',
        'icon': 'Grid3x3',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'ndim': 2,
                    'dims': [
                        {'param': 'position_dim', 'default': 'position'},
                        {'param': 'base_dim', 'default': 'base'},
                    ],
                    'labels': [],
                    'parallel': [],
                }
            ],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                },
            },
        },
        'resources': {'estimate': 'estimate_memory', 'memory_modes': ['full'], 'supports_cuda': False},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for item in inputs:
            data = getattr(item, 'data', None)
            if data is not None:
                size += int(np.asarray(data).nbytes)
        return (max(size * 2, 4 * 1024 * 1024), 1024 * 1024)

    def run(self, ctx: Context, inputs):
        counts_form = inputs[0]
        position_dim = str(ctx.step_params.get('position_dim', 'position'))
        base_dim = str(ctx.step_params.get('base_dim', 'base'))
        pseudocount = float(ctx.step_params.get('pseudocount', 0.5))
        background = parse_background(ctx.step_params.get('background', '0.25,0.25,0.25,0.25'))
        out_name = str(ctx.step_params.get('output', 'pwm'))

        if pseudocount < 0:
            raise StepError('pwm_from_counts: pseudocount must be non-negative')
        counts = counts_matrix(counts_form, position_dim, base_dim)
        pwm, probabilities = pwm_matrix(counts, pseudocount, background)
        ic = information_content(probabilities, background)

        data = pwm.astype(np.float32)
        form = Form(
            data,
            dims=[position_dim, base_dim],
            labels={
                position_dim: {label: index for index, label in enumerate(counts_form.labels[position_dim])},
                base_dim: {base: index for index, base in enumerate(BASES)},
            },
            info={
                'background': [float(value) for value in background],
                'pseudocount': pseudocount,
                'consensus': best_base(probabilities),
                'information_content': [float(value) for value in ic],
                'total_information': float(ic.sum()),
                'n_positions': int(pwm.shape[0]),
                'total_sites': float(counts.sum(axis=1).mean()),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            'n_positions': int(pwm.shape[0]),
            'consensus': form.info['consensus'],
            'total_information': float(ic.sum()),
        }

    def export(self, ctx):
        return dict(self._export_data)
