"""Peak quality for ATAC-seq: FRiP, peak widths and fragments per peak.

Inputs:
    A  FileArtifact (format bam)
    B  BED [peak, field] with chrom / chromStart / chromEnd
Output:
    2D Form [statistic, value]
"""
from __future__ import annotations

import bisect

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._atac_utils import bam_path, bed_records, iter_fragments

_LABELS = (
    'n_fragments',
    'n_peaks',
    'total_peak_bp',
    'mean_peak_width',
    'median_peak_width',
    'fragments_in_peaks',
    'frip',
    'fragments_per_peak',
)


class AtacPeakQualityStep(Step):
    """Fraction of reads in peaks and peak width statistics."""
    provider = 'operon-core'
    parameters_file = 'atac_peak_quality.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'atac_peak_quality',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'atac_peak_quality',
        'description': 'FRiP and peak width statistics for ATAC-seq (BAM + peak BED).',
        'category': 'Quality Control',
        'icon': 'Gauge',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0,
                 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['bam']}}},
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'peak_region_dim', 'default': 'region'},
                          {'param': 'peak_field_dim', 'default': 'field'}],
                 'labels': [],
                 'info': {'encoders': {'type': 'object', 'optional': True}}},
            ],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.2), 32 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2 or not isinstance(inputs[0], FileArtifact):
            raise StepError('atac_peak_quality requires a BAM file and a peak BED')
        params = ctx.step_params
        out_name = params.get('output', 'peak_quality')

        peaks = bed_records(
            inputs[1],
            region_dim=params.get('peak_region_dim', 'region'),
            field_dim=params.get('peak_field_dim', 'field'),
            chrom_field=params.get('peak_chrom_field', 'chrom'),
            start_field=params.get('peak_start_field', 'chromStart'),
            end_field=params.get('peak_end_field', 'chromEnd'),
            strand_field=params.get('peak_strand_field', 'strand'))
        if not peaks:
            raise StepError('peak BED has no records')

        per_chrom = {}
        for chrom, start, end, _strand in peaks:
            per_chrom.setdefault(chrom, []).append((start, end))
        lookup = {}
        for chrom, intervals in per_chrom.items():
            intervals.sort()
            starts = [item[0] for item in intervals]
            ends = [item[1] for item in intervals]
            prefix = []
            best = -1
            for value in ends:
                best = max(best, value)
                prefix.append(best)
            lookup[chrom] = (starts, prefix)

        widths = np.array([end - start for _c, start, end, _s in peaks], dtype=np.float64)
        n_fragments = 0
        in_peaks = 0
        for chrom, start, end in iter_fragments(
                bam_path(inputs[0], 'atac_peak_quality'),
                min_mapq=int(params.get('min_mapq', 30)),
                max_records=int(params.get('max_records', 0)),
                exclude_duplicates=bool(params.get('exclude_duplicates', True))):
            n_fragments += 1
            entry = lookup.get(chrom)
            if entry is None:
                continue
            starts, prefix = entry
            index = bisect.bisect_left(starts, end)
            if index > 0 and prefix[index - 1] > start:
                in_peaks += 1

        if n_fragments == 0:
            raise StepError('no fragments passed the filters')
        frip = in_peaks / n_fragments
        values = [
            float(n_fragments),
            float(len(peaks)),
            float(widths.sum()),
            float(widths.mean()),
            float(np.median(widths)),
            float(in_peaks),
            float(frip),
            float(in_peaks / len(peaks)),
        ]
        data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
        labels = {'statistic': {name: index for index, name in enumerate(_LABELS)},
                  'value': {'value': 0}}
        info = {
            'n_fragments': n_fragments,
            'n_peaks': len(peaks),
            'fragments_in_peaks': in_peaks,
            'frip': frip,
            'mean_peak_width': float(widths.mean()),
            'median_peak_width': float(np.median(widths)),
        }
        out = Form(data, ['statistic', 'value'], labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info, output=out_name)

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
