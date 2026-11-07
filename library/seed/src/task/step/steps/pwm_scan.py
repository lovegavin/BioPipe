"""Scan sequences with a position weight matrix."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from src.task.step.steps._annotation_utils import fasta_sequences
from src.task.step.steps._pwm_utils import BASES, read_pwm, scan_pwm


class PwmScanStep(Step):
    """Report PWM hits above a score threshold on one or both strands."""

    provider = 'operon-core'
    parameters_file = 'pwm_scan.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'pwm_scan',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'pwm_scan',
        'description': 'Scan sequences for PWM matches above a log-odds threshold.',
        'category': 'Sequence',
        'icon': 'Search',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': False,
                    'ndim': 2,
                    'dims': [
                        {'param': 'sequence_dim', 'default': 'sequence'},
                        {'param': 'position_dim', 'default': 'position'},
                    ],
                    'labels': [],
                    'parallel': [],
                },
                {
                    'version': 1,
                    'numeric': True,
                    'ndim': 2,
                    'dims': [
                        {'param': 'pwm_position_dim', 'default': 'position'},
                        {'param': 'base_dim', 'default': 'base'},
                    ],
                    'labels': [],
                    'parallel': [],
                },
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
        'inputs_arity': 2,
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
        return (max(size * 3, 8 * 1024 * 1024), 1024 * 1024)

    def run(self, ctx: Context, inputs):
        sequences = inputs[0]
        pwm_form = inputs[1]
        sequence_dim = str(ctx.step_params.get('sequence_dim', 'sequence'))
        position_dim = str(ctx.step_params.get('position_dim', 'position'))
        pwm_position_dim = str(ctx.step_params.get('pwm_position_dim', 'position'))
        base_dim = str(ctx.step_params.get('base_dim', 'base'))
        min_score = float(ctx.step_params.get('min_score', 8.0))
        both_strands = bool(ctx.step_params.get('both_strands', True))
        max_hits = int(ctx.step_params.get('max_hits', 0) or 0)
        out_name = str(ctx.step_params.get('output', 'hits'))

        if max_hits < 0:
            raise StepError('pwm_scan: max_hits must be non-negative')
        pwm = read_pwm(pwm_form, pwm_position_dim, base_dim)
        names, texts = fasta_sequences(sequences, sequence_dim, position_dim, 'pwm_scan')

        rows = []
        labels = []
        per_sequence = []
        total_hits = 0
        best = None
        for name, text in zip(names, texts):
            hits = scan_pwm(pwm, text, min_score, both_strands)
            if max_hits:
                hits = hits[:max_hits]
            per_sequence.append(len(hits))
            total_hits += len(hits)
            for position, strand, score, _site in hits:
                rows.append((float(position), 1.0 if strand == '+' else -1.0, float(score)))
                labels.append(f"{name}:{position}:{strand}")
                if best is None or score > best[0]:
                    best = (score, name, position, strand)
        if not rows:
            empty = np.zeros((0, 3), dtype=np.float32)
            form = Form(
                empty,
                dims=['hit', 'field'],
                labels={'hit': {}, 'field': {'position': 0, 'strand': 1, 'score': 2}},
                info={
                    'n_sequences': len(names),
                    'n_hits': 0,
                    'min_score': min_score,
                    'both_strands': both_strands,
                    'hits_per_kb': 0.0,
                },
            )
            form.validate()
            ctx[out_name] = form
            self._export_data = {'n_sequences': len(names), 'n_hits': 0, 'min_score': min_score}
            return

        data = np.asarray(rows, dtype=np.float32)
        form = Form(
            data,
            dims=['hit', 'field'],
            labels={
                'hit': {label: index for index, label in enumerate(labels)},
                'field': {'position': 0, 'strand': 1, 'score': 2},
            },
            info={
                'n_sequences': len(names),
                'n_hits': total_hits,
                'min_score': min_score,
                'both_strands': both_strands,
                'hits_per_kb': float(total_hits) * 1000.0 / max(1, sum(len(text) for text in texts)),
                'hits_per_sequence': per_sequence,
                'best_score': float(best[0]) if best else None,
                'best_hit': {'sequence': best[1], 'position': int(best[2]), 'strand': best[3]} if best else None,
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            'n_sequences': len(names),
            'n_hits': total_hits,
            'min_score': min_score,
            'best_score': float(best[0]) if best else None,
        }

    def export(self, ctx):
        return dict(self._export_data)
