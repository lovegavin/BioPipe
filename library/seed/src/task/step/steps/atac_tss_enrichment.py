"""TSS enrichment matrix for ATAC-seq fragments.

Inputs:
    A  FileArtifact (format bam)
    B  BED [tss, field] with chrom / chromStart / chromEnd / strand
Output:
    2D Form [tss, position] with fragment-midpoint counts per bin, plus the
    aggregate profile and the center/flank enrichment score in ``info``.
"""
from __future__ import annotations

import bisect
import math

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._atac_utils import bam_path, bed_records, iter_fragments


class AtacTssEnrichmentStep(Step):
    """Count ATAC-seq fragment midpoints around transcription start sites."""
    provider = 'operon-core'
    parameters_file = 'atac_tss_enrichment.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'atac_tss_enrichment',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'atac_tss_enrichment',
        'description': 'Per-TSS fragment-density matrix and TSS enrichment score (ATAC-seq QC).',
        'category': 'Quality Control',
        'icon': 'Activity',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0,
                 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['bam']}}},
                {'version': 1, 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'tss_region_dim', 'default': 'region'},
                          {'param': 'tss_field_dim', 'default': 'field'}],
                 'labels': [],
                 'info': {'encoders': {'type': 'object', 'optional': True}}},
            ],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True,
                                                     'axis_info_open': True}},
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
        return max(int(size * 0.2), 32 * 1024 ** 2), 8 * 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2 or not isinstance(inputs[0], FileArtifact):
            raise StepError('atac_tss_enrichment requires a BAM file and a TSS BED')
        params = ctx.step_params
        out_name = params.get('output', 'tss_enrichment')
        flank = int(params.get('flank', 500))
        bin_size = int(params.get('bin_size', 10))
        if flank < 1 or bin_size < 1 or flank % bin_size:
            raise StepError('flank must be a positive multiple of bin_size')
        n_bins = (2 * flank) // bin_size

        tss_rows = bed_records(
            inputs[1],
            region_dim=params.get('tss_region_dim', 'region'),
            field_dim=params.get('tss_field_dim', 'field'),
            chrom_field=params.get('tss_chrom_field', 'chrom'),
            start_field=params.get('tss_start_field', 'chromStart'),
            end_field=params.get('tss_end_field', 'chromEnd'),
            strand_field=params.get('tss_strand_field', 'strand'))
        if not tss_rows:
            raise StepError('TSS BED has no records')

        sites = []
        used = {}
        for chrom, start, end, strand in tss_rows:
            position = start if strand != '-' else end - 1
            base = f"{chrom}:{position}:{strand}"
            seen = used.get(base, 0) + 1
            used[base] = seen
            label = base if seen == 1 else f"{base}#{seen}"
            sites.append((chrom, position, label))

        offsets = np.array([-flank + bin_size / 2 + index * bin_size
                            for index in range(n_bins)], dtype=np.float64)
        by_chrom = {}
        for index, (chrom, position, _label) in enumerate(sites):
            by_chrom.setdefault(chrom, []).append((position, index))
        for entries in by_chrom.values():
            entries.sort()
        positions = {chrom: [entry[0] for entry in entries]
                     for chrom, entries in by_chrom.items()}
        index_map = {chrom: [entry[1] for entry in entries]
                     for chrom, entries in by_chrom.items()}

        counts = np.zeros((len(sites), n_bins), dtype=np.float64)
        n_fragments = 0
        for chrom, start, end in iter_fragments(
                bam_path(inputs[0], 'atac_tss_enrichment'),
                min_mapq=int(params.get('min_mapq', 30)),
                max_records=int(params.get('max_records', 0)),
                exclude_duplicates=bool(params.get('exclude_duplicates', True))):
            if chrom not in by_chrom:
                continue
            n_fragments += 1
            midpoint = (start + end) // 2
            chrom_positions = positions[chrom]
            left = bisect.bisect_left(chrom_positions, midpoint - flank)
            right = bisect.bisect_right(chrom_positions, midpoint + flank)
            for slot in range(left, right):
                tss_position = chrom_positions[slot]
                offset = midpoint - tss_position
                index = int(math.floor((offset + flank) / bin_size))
                if 0 <= index < n_bins:
                    counts[index_map[chrom][slot], index] += 1

        profile = counts.mean(axis=0) if len(sites) else np.zeros(n_bins)
        center = np.abs(offsets) < 50
        flank_mask = (np.abs(offsets) >= flank - 50) & (np.abs(offsets) < flank)
        center_mean = float(profile[center].mean()) if center.any() else 0.0
        flank_mean = float(profile[flank_mask].mean()) if flank_mask.any() else 0.0
        score = center_mean / flank_mean if flank_mean > 0 else 0.0

        labels = {
            'tss': {label: index for index, (_c, _p, label) in enumerate(sites)},
            'position': {f"{value:g}": index for index, value in enumerate(offsets)},
        }
        info = {
            'n_tss': len(sites),
            'n_fragments': n_fragments,
            'flank': flank,
            'bin_size': bin_size,
            'n_bins': n_bins,
            'tss_score': score,
            'center_mean': center_mean,
            'flank_mean': flank_mean,
            'offsets': [float(value) for value in offsets],
            'profile': [float(value) for value in profile],
        }
        out = Form(counts, ['tss', 'position'], labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            'n_tss': len(sites),
            'n_fragments': n_fragments,
            'tss_score': score,
            'center_mean': center_mean,
            'flank_mean': flank_mean,
            'output': out_name,
        }

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
