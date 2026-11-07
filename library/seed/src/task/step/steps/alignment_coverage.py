"""Compute genome-wide depth-of-coverage statistics from a BAM file.

Input: FileArtifact (format bam).
Output: 2D Form [statistic, value].

Depth is accumulated with a difference array, so memory is proportional to the
reference length rather than to the number of reads.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._bam_utils import iter_records, read_header

_LABELS = (
    "n_reads",
    "n_mapped",
    "n_references",
    "genome_length",
    "mean_depth",
    "covered_bases",
    "breadth_1x",
    "breadth_5x",
    "breadth_10x",
    "max_depth",
)


class AlignmentCoverageStep(Step):
    """Summarise depth of coverage like ``samtools coverage``."""
    provider = 'operon-core'
    parameters_file = 'alignment_coverage.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'alignment_coverage',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'alignment_coverage',
        'description': 'Summarise mapped depth across the reference (samtools coverage compatible).',
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
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.25), 16 * 1024 ** 2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError('alignment_coverage requires a BAM file artifact')
        artifact = inputs[0]
        artifact.validate()
        if artifact.format != 'bam':
            raise StepError(f'alignment_coverage requires a BAM file, got {artifact.format!r}')
        params = dict(ctx.step_params)
        min_mapq = int(params.get('min_mapq') or 0)
        max_records = int(params.get('max_records') or 0)
        out_name = params.get('output') or self.name
        path = next(iter(artifact.files.values()))

        try:
            _text, references = read_header(path)
        except ValueError as exc:
            raise StepError(f'alignment_coverage: {exc}') from exc
        if not references:
            raise StepError('alignment_coverage: BAM header has no references')

        offsets = {}
        total = 0
        for name, length in references:
            offsets[name] = total
            total += length
        diff = np.zeros(total + 1, dtype=np.int64)
        n_reads = 0
        n_mapped = 0
        primary_skip = 0x100 | 0x800
        try:
            for record in iter_records(path, max_records=max_records):
                n_reads += 1
                flag = record['flag']
                if flag & primary_skip or flag & 0x4:
                    continue
                ref_id = record['ref_id']
                if ref_id < 0 or ref_id >= len(references):
                    continue
                n_mapped += 1
                base = offsets[references[ref_id][0]]
                position = base + record['pos']
                for op, length in record['cigar']:
                    if op in 'M=X':
                        if position < total:
                            diff[position] += 1
                            diff[position + length] -= 1
                        position += length
                    elif op in 'DN':
                        position += length
        except ValueError as exc:
            raise StepError(f'alignment_coverage: {exc}') from exc

        depth = np.cumsum(diff[:-1])
        covered = int(np.count_nonzero(depth))
        genome_length = total
        mean_depth = float(depth.sum() / genome_length) if genome_length else 0.0
        metrics = {
            'n_reads': n_reads,
            'n_mapped': n_mapped,
            'n_references': len(references),
            'genome_length': genome_length,
            'mean_depth': mean_depth,
            'covered_bases': covered,
            'breadth_1x': covered / genome_length if genome_length else 0.0,
            'breadth_5x': int(np.count_nonzero(depth >= 5)) / genome_length if genome_length else 0.0,
            'breadth_10x': int(np.count_nonzero(depth >= 10)) / genome_length if genome_length else 0.0,
            'max_depth': int(depth.max()) if depth.size else 0,
        }
        data = np.asarray([[float(metrics[label])] for label in _LABELS], dtype=float)
        labels = {
            'statistic': {label: index for index, label in enumerate(_LABELS)},
            'value': {'value': 0},
        }
        info = {'source_format': artifact.format, 'min_mapq': min_mapq}
        ctx[out_name] = Form(data=data, dims=['statistic', 'value'], labels=labels, info=info)
        self._export_data = dict(metrics)
        print(
            f"[alignment_coverage] {metrics['genome_length']} bp, "
            f"mean depth {metrics['mean_depth']:.4f}x, breadth1x {metrics['breadth_1x']:.4f}"
        )

    def export(self, ctx):
        return self._export_data
