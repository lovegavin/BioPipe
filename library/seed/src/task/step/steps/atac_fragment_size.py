"""Fragment-length histogram and nucleosome fractions from an ATAC-seq BAM.

Input:  FileArtifact (format bam)
Output: 2D Form [length, statistic] with counts and fractions
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._atac_utils import bam_path, iter_fragments


class AtacFragmentSizeStep(Step):
    """Histogram of ATAC-seq fragment lengths."""
    provider = 'operon-core'
    parameters_file = 'atac_fragment_size.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'atac_fragment_size',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'atac_fragment_size',
        'description': 'Fragment length histogram and NFR/mono/dinucleosome fractions (ATAC-seq QC).',
        'category': 'Quality Control',
        'icon': 'BarChart3',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'kind': 'file',
                'numeric': False,
                'ndim': 0,
                'dims': [],
                'info': {'representation': {'type': 'string', 'enum': ['bam']}},
            }],
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
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.15), 16 * 1024 ** 2), 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError('atac_fragment_size requires a BAM file artifact')
        params = ctx.step_params
        out_name = params.get('output', 'fragment_size')
        max_length = int(params.get('max_length', 1000))
        min_length = int(params.get('min_length', 0))
        if max_length < min_length or max_length < 1:
            raise StepError('max_length must be >= min_length and >= 1')

        counts = np.zeros(max_length + 1, dtype=np.int64)
        lengths = []
        for _chrom, start, end in iter_fragments(
                bam_path(inputs[0], 'atac_fragment_size'),
                min_mapq=int(params.get('min_mapq', 30)),
                max_records=int(params.get('max_records', 0)),
                exclude_duplicates=bool(params.get('exclude_duplicates', True))):
            length = int(end - start)
            if min_length <= length <= max_length:
                counts[length] += 1
                lengths.append(length)

        n = int(counts.sum())
        if n == 0:
            raise StepError('no fragments passed the filters')
        values = np.arange(max_length + 1)
        used = counts[min_length:] if min_length else counts
        rows = np.zeros((used.size, 2), dtype=np.float64)
        rows[:, 0] = counts[min_length:]
        rows[:, 1] = rows[:, 0] / n
        dims = ['length', 'statistic']
        labels = {'length': {str(int(v)): i for i, v in enumerate(values[min_length:])},
                  'statistic': {'fragments': 0, 'fraction': 1}}

        arr = np.asarray(lengths, dtype=np.int64)
        nfr = float((arr < 100).sum()) / n
        mono = float(((arr >= 180) & (arr <= 247)).sum()) / n
        di = float(((arr >= 300) & (arr <= 400)).sum()) / n
        nucleosome = float((arr >= 147).sum()) / n
        info = {
            'n_fragments': n,
            'mean_length': float(arr.mean()),
            'median_length': float(np.median(arr)),
            'nfr_fraction': nfr,
            'mononucleosome_fraction': mono,
            'dinucleosome_fraction': di,
            'nucleosome_fraction': nucleosome,
            'max_length': max_length,
            'min_length': min_length,
        }
        out = Form(rows, dims, labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info, output=out_name)

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
