"""Normalise a gene count table to TPM, FPKM and CPM.

Input:  2D Form [feature, statistic] with counts and length columns
Output: 2D Form [feature, statistic] with tpm, fpkm and cpm
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def column_index(form: Form, column: str, operator: str) -> int:
    labels = (form.labels or {}).get('statistic') or {}
    if column in labels:
        return int(labels[column])
    raise StepError(f"{operator}: input has no '{column}' column")


class CountsNormalizeStep(Step):
    """Convert raw counts with gene lengths into TPM, FPKM and CPM."""
    provider = 'operon-core'
    parameters_file = 'counts_normalize.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'counts_normalize',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'counts_normalize',
        'description': 'TPM, FPKM and CPM from a gene count table with lengths.',
        'category': 'Omics',
        'icon': 'Calculator',
        'contracts': {
            'version': 1,
            'inputs': [{'version': 1, 'kind': 'form', 'numeric': True, 'ndim': 2,
                        'dims': ['feature', 'statistic'],
                        'labels': []}],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True,
                                                     'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], 'nbytes', 0) or 0) if inputs else 0
        return max(size * 3, 4 * 1024 ** 2), 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError('counts_normalize requires a count table')
        params = ctx.step_params
        out_name = params.get('output', 'normalized')
        form = inputs[0]
        data = np.asarray(form.data, dtype=np.float64)
        if data.ndim != 2:
            raise StepError('counts_normalize expects a 2D table')
        count_col = column_index(form, str(params.get('count_column', 'counts')), 'counts_normalize')
        length_col = column_index(form, str(params.get('length_column', 'length')), 'counts_normalize')
        counts = data[:, count_col]
        lengths = data[:, length_col]
        if np.any(counts < 0) or np.any(lengths <= 0):
            raise StepError('counts must be non-negative and lengths must be positive')

        total = float(counts.sum())
        if total <= 0:
            raise StepError('the count table is empty')
        rate = counts / (lengths / 1000.0)
        rate_total = float(rate.sum())
        if rate_total <= 0:
            raise StepError('the count table is empty')
        tpm = rate / rate_total * 1e6
        fpkm = rate / (total / 1e6)
        cpm = counts / total * 1e6
        out_data = np.column_stack([tpm, fpkm, cpm])
        labels = {
            'feature': dict((form.labels or {}).get('feature') or {}),
            'statistic': {'tpm': 0, 'fpkm': 1, 'cpm': 2},
        }
        if not labels['feature']:
            labels['feature'] = {str(i): i for i in range(out_data.shape[0])}
        info = {
            'n_features': int(out_data.shape[0]),
            'total_counts': total,
            'method': 'tpm/fpkm/cpm',
        }
        out = Form(out_data, ['feature', 'statistic'], labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info, output=out_name)

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
