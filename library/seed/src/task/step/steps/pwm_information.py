"""Summarize information content of a log-odds PWM."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from src.task.step.steps._pwm_utils import BASES, best_base, information_content, parse_background, read_pwm


class PwmInformationStep(Step):
    """Per-position information content and consensus of a PWM."""

    provider = 'operon-core'
    parameters_file = 'pwm_information.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'pwm_information',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'pwm_information',
        'description': 'Compute per-position information content and consensus of a PWM.',
        'category': 'Sequence',
        'icon': 'BarChart3',
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
        pwm_form = inputs[0]
        position_dim = str(ctx.step_params.get('position_dim', 'position'))
        base_dim = str(ctx.step_params.get('base_dim', 'base'))
        background = parse_background(ctx.step_params.get('background', '0.25,0.25,0.25,0.25'))
        out_name = str(ctx.step_params.get('output', 'information'))

        pwm = read_pwm(pwm_form, position_dim, base_dim)
        odds = np.power(2.0, pwm) * background[None, :]
        totals = odds.sum(axis=1, keepdims=True)
        if np.any(totals <= 0) or not np.isfinite(totals).all():
            raise StepError('pwm_information: PWM scores produce invalid probabilities')
        probabilities = odds / totals
        ic = information_content(probabilities, background)
        peak = probabilities.max(axis=1)

        data = np.column_stack([ic, peak]).astype(np.float32)
        form = Form(
            data,
            dims=[position_dim, 'statistic'],
            labels={
                position_dim: {label: index for index, label in enumerate(pwm_form.labels[position_dim])},
                'statistic': {'information_content': 0, 'consensus_probability': 1},
            },
            info={
                'total_information': float(ic.sum()),
                'mean_information': float(ic.mean()),
                'consensus': best_base(probabilities),
                'max_position_information': int(np.argmax(ic)),
                'background': [float(value) for value in background],
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            'n_positions': int(pwm.shape[0]),
            'total_information': float(ic.sum()),
            'consensus': form.info['consensus'],
        }

    def export(self, ctx):
        return dict(self._export_data)
