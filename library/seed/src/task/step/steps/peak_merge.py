"""Merge nearby peaks within a maximum gap."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class PeakMergeStep(Step):
    """Merge overlapping or nearby peaks per chromosome."""
    provider = 'operon-core'
    parameters_file = 'peak_merge.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'peak_merge',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'peak_merge',
        'description': 'Merge peaks that overlap or are closer than max_gap on the same chromosome.',
        'category': 'Genome',
        'icon': 'Filter',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'kind': 'form',
                'numeric': True,
                'ndim': 2,
                'dims': [{'param': 'peak_dim', 'default': 'peak'},
                         {'param': 'field_dim', 'default': 'field'}],
                'info_open': True,
            }],
            'output': {'mode': 'declare', 'schema': {
                'ndim': 2, 'numeric': True, 'info_open': True,
                'labels': {'field': ['start', 'end', 'length', 'n_merged']}}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'nbytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.2), 16 * 1024 ** 2), 8 * 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], Form):
            raise StepError('peak_merge requires a peak table Form')
        form = inputs[0]
        params = ctx.step_params
        out_name = params.get('output', 'merged')
        max_gap = int(params.get('max_gap', 50))
        peak_dim = params.get('peak_dim', 'peak')
        field_dim = params.get('field_dim', 'field')
        if max_gap < 0:
            raise StepError('max_gap must be non-negative')

        fields = {name: index for name, index in form.labels[field_dim].items()}
        for required in ('start', 'end'):
            if required not in fields:
                raise StepError(f'peak_merge requires a {required!r} column')
        start_col = fields['start']
        end_col = fields['end']
        chroms = (form.info or {}).get('chrom')
        data = np.asarray(form.data, dtype=np.float64)
        if chroms is None:
            chroms = [''] * data.shape[0]
        if len(chroms) != data.shape[0]:
            raise StepError('peak_merge requires one chrom value per peak')

        grouped = defaultdict(list)
        for row, chrom in zip(data, chroms):
            grouped[chrom].append((int(row[start_col]), int(row[end_col])))

        merged = []
        for chrom in sorted(grouped):
            intervals = sorted(grouped[chrom])
            current_start, current_end, count = intervals[0][0], intervals[0][1], 1
            for start, end in intervals[1:]:
                if start - current_end <= max_gap:
                    current_end = max(current_end, end)
                    count += 1
                else:
                    merged.append((chrom, current_start, current_end, count))
                    current_start, current_end, count = start, end, 1
            merged.append((chrom, current_start, current_end, count))

        rows = np.asarray([[start, end, end - start, count]
                           for _chrom, start, end, count in merged], dtype=np.float64)
        if rows.size == 0:
            rows = np.zeros((0, 4), dtype=np.float64)
        labels = {f'peak_{index}': index for index in range(len(merged))}
        info = {'chrom': [item[0] for item in merged],
                'n_input': int(data.shape[0]),
                'n_merged': len(merged),
                'max_gap': max_gap}
        form_out = Form(rows, dims=['peak', 'field'],
                        labels={'peak': labels,
                                'field': dict((f, i) for i, f in enumerate(
                                    ('start', 'end', 'length', 'n_merged')))},
                        info=info)
        form_out.validate()
        ctx[out_name] = form_out
        self._export_data = {'n_input': int(data.shape[0]), 'n_merged': len(merged),
                             'max_gap': max_gap,
                             'merged_bp': int(sum(end - start for _c, start, end, _n in merged))}

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)
