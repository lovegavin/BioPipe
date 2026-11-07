"""Summarise the paired-read insert-size distribution of a BAM file.

Input: FileArtifact (format bam).
Output: 2D Form [statistic, value].
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._bam_utils import iter_records

_LABELS = (
    "n_pairs",
    "mean_insert_size",
    "median_insert_size",
    "std_insert_size",
    "min_insert_size",
    "max_insert_size",
    "p25_insert_size",
    "p75_insert_size",
)

_FLAG_PAIRED = 0x1
_FLAG_UNMAPPED = 0x4
_FLAG_MATE_UNMAPPED = 0x8
_FLAG_READ1 = 0x40
_FLAG_SECONDARY = 0x100
_FLAG_SUPPLEMENTARY = 0x800


class AlignmentInsertSizeStep(Step):
    """Summarise insert sizes of primary, properly mapped read pairs."""
    provider = 'operon-core'
    parameters_file = 'alignment_insert_size.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'alignment_insert_size',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'alignment_insert_size',
        'description': 'Summarise paired-read insert sizes (samtools stats compatible).',
        'category': 'Quality Control',
        'icon': 'Ruler',
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
        return max(int(size * 0.1), 8 * 1024 ** 2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError('alignment_insert_size requires a BAM file artifact')
        artifact = inputs[0]
        artifact.validate()
        if artifact.format != 'bam':
            raise StepError(f'alignment_insert_size requires a BAM file, got {artifact.format!r}')
        params = dict(ctx.step_params)
        min_mapq = int(params.get('min_mapq') or 0)
        max_records = int(params.get('max_records') or 0)
        out_name = params.get('output') or self.name
        path = next(iter(artifact.files.values()))

        sizes = []
        try:
            for record in iter_records(path, max_records=max_records):
                flag = record['flag']
                if flag & (_FLAG_SECONDARY | _FLAG_SUPPLEMENTARY):
                    continue
                if not flag & _FLAG_PAIRED or flag & _FLAG_UNMAPPED or flag & _FLAG_MATE_UNMAPPED:
                    continue
                if not flag & _FLAG_READ1:
                    continue
                if record['mapq'] < min_mapq:
                    continue
                tlen = record['tlen']
                if tlen:
                    sizes.append(abs(tlen))
        except ValueError as exc:
            raise StepError(f'alignment_insert_size: {exc}') from exc
        if not sizes:
            raise StepError('alignment_insert_size: no paired reads with a nonzero insert size')
        values = np.asarray(sizes, dtype=float)
        metrics = {
            'n_pairs': int(values.size),
            'mean_insert_size': float(values.mean()),
            'median_insert_size': float(np.median(values)),
            'std_insert_size': float(values.std(ddof=0)),
            'min_insert_size': float(values.min()),
            'max_insert_size': float(values.max()),
            'p25_insert_size': float(np.percentile(values, 25)),
            'p75_insert_size': float(np.percentile(values, 75)),
        }
        data = np.asarray([[metrics[label]] for label in _LABELS], dtype=float)
        labels = {
            'statistic': {label: index for index, label in enumerate(_LABELS)},
            'value': {'value': 0},
        }
        info = {'source_format': artifact.format, 'min_mapq': min_mapq}
        ctx[out_name] = Form(data=data, dims=['statistic', 'value'], labels=labels, info=info)
        self._export_data = dict(metrics)
        print(
            f"[alignment_insert_size] {metrics['n_pairs']} pairs, mean {metrics['mean_insert_size']:.2f}, "
            f"median {metrics['median_insert_size']:.2f}"
        )

    def export(self, ctx):
        return self._export_data
