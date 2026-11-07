"""Poisson peak calling for ATAC-seq / ChIP-seq BAM files."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_utils import call_peaks, read_references

_FIELDS = ('start', 'end', 'length', 'summit', 'count', 'score', 'fold_enrichment')


class AtacPeakCallStep(Step):
    """Call peaks from fragment pileup with a local Poisson model."""
    provider = 'operon-core'
    parameters_file = 'atac_peak_call.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'atac_peak_call',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'atac_peak_call',
        'description': 'Call ATAC/ChIP peaks from a BAM file with a local Poisson model and BH q-values.',
        'category': 'Quality Control',
        'icon': 'ChartBar',
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
            'output': {'mode': 'declare', 'schema': {
                'ndim': 2, 'numeric': True, 'info_open': True,
                'labels': {'field': ['start', 'end', 'length', 'summit',
                                     'count', 'score', 'fold_enrichment']}}},
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
        return max(int(size * 0.5) + 3 * 1024 ** 3, 3 * 1024 ** 3), 2 * 1024 ** 3

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError('atac_peak_call requires a BAM file artifact')
        params = ctx.step_params
        out_name = params.get('output', 'peaks')
        qvalue = float(params.get('qvalue', 0.05))
        if not 0 < qvalue < 1:
            raise StepError('qvalue must be between 0 and 1')
        max_gap = int(params.get('max_gap', 50))
        min_length = int(params.get('min_length', 100))
        if min_length < 1:
            raise StepError('min_length must be positive')
        candidate_sigma = float(params.get('candidate_sigma', 3.0))
        if candidate_sigma <= 0:
            raise StepError('candidate_sigma must be positive')
        extension_bp = int(params.get('extension_bp', 260))
        if extension_bp < 0:
            raise StepError('extension_bp must be non-negative')
        path = next(iter(inputs[0].files.values()))
        names, lengths = read_references(path)
        chrom_lengths = dict(zip(names, lengths))
        genome_bp = int(sum(lengths))

        grouped = defaultdict(lambda: ([], []))
        total_bp = 0
        n_fragments = 0
        max_fragments = int(params.get('max_fragments', 0))
        from src.task.step.steps._peak_utils import iter_fragments
        for chrom, start, end in iter_fragments(
                path, min_mapq=int(params.get('min_mapq', 30)),
                max_fragments=max_fragments):
            starts, ends = grouped[chrom]
            starts.append(start)
            ends.append(end)
            total_bp += end - start
            n_fragments += 1
        if n_fragments == 0:
            raise StepError('no fragments passed the filters')
        fragments = {chrom: (np.asarray(values[0], dtype=np.int64),
                             np.asarray(values[1], dtype=np.int64))
                     for chrom, values in grouped.items()}
        peaks = call_peaks(
            fragments, chrom_lengths, qvalue=qvalue, max_gap=max_gap,
            min_length=min_length,
            local_windows=(int(params.get('window_1kb', 1000)),
                           int(params.get('window_10kb', 10000))),
            candidate_sigma=candidate_sigma, extension_bp=extension_bp,
            total_fragments_bp=total_bp, genome_bp=genome_bp)

        rows = np.asarray([[p[field] for field in _FIELDS] for p in peaks],
                          dtype=np.float64)
        if rows.size == 0:
            rows = np.zeros((0, len(_FIELDS)), dtype=np.float64)
        labels = {f'peak_{index}': index for index in range(len(peaks))}
        info = {
            'chrom': [p['chrom'] for p in peaks],
            'n_peaks': len(peaks),
            'n_fragments': n_fragments,
            'fragment_bp': total_bp,
            'genome_bp': genome_bp,
            'qvalue': qvalue,
            'max_gap': max_gap,
            'min_length': min_length,
            'candidate_sigma': candidate_sigma,
            'extension_bp': extension_bp,
        }
        form = Form(rows, dims=['peak', 'field'],
                    labels={'peak': labels, 'field': dict((f, i) for i, f in enumerate(_FIELDS))},
                    info=info)
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            'n_peaks': len(peaks),
            'n_fragments': n_fragments,
            'peak_bp': int(sum(p['length'] for p in peaks)),
            'qvalue': qvalue,
            'candidate_sigma': candidate_sigma,
            'extension_bp': extension_bp,
            'n_chromosomes': len(grouped),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)
