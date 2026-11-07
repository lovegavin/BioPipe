"""Remove 3' adapter sequence from FASTQ reads without indels."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._fastq_transform import (
    adapter_trim_index,
    fastq_path,
    read_fastq,
    write_fastq_file,
)
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_LABELS = (
    "reads_in",
    "reads_with_adapter",
    "reads_out",
    "bases_in",
    "bases_out",
    "bases_trimmed",
    "mean_length_in",
    "mean_length_out",
    "output_bytes",
)


class FastqAdapterTrimStep(Step):
    """Trim a 3' adapter with an exact (no-indel) leftmost match."""

    provider = 'operon-core'
    parameters_file = 'fastq_adapter_trim.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'fastq_adapter_trim',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'fastq_adapter_trim',
        'description': 'Trim a 3-prime adapter using an exact, no-indel match.',
        'category': 'Quality Control',
        'icon': 'Filter',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'kind': 'file',
                    'numeric': False,
                    'ndim': 0,
                    'dims': [],
                    'info': {'representation': {'type': 'string', 'enum': ['fastq', 'fq']}},
                }
            ],
            'output': {
                'mode': 'declare',
                'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True},
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 1.5), 16 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError('fastq_adapter_trim requires a FASTQ file artifact')
        path = fastq_path(inputs[0], 'fastq_adapter_trim')
        params = dict(ctx.step_params)
        adapter = str(params.get('adapter') or '').strip().upper()
        min_overlap = int(params.get('min_overlap') or 3)
        max_mismatches = int(params.get('max_mismatches') or 0)
        max_records = int(params.get('max_records') or 0)
        if not adapter:
            raise StepError('fastq_adapter_trim: adapter sequence is required')
        if min_overlap < 1:
            raise StepError('fastq_adapter_trim: min_overlap must be at least 1')
        out_name = params.get('output') or self.name

        kept = []
        reads_in = 0
        with_adapter = 0
        bases_in = 0
        bases_out = 0
        try:
            for header, sequence, plus, quality in read_fastq(path):
                if max_records and reads_in >= max_records:
                    break
                reads_in += 1
                bases_in += len(sequence)
                cut = adapter_trim_index(sequence, adapter, min_overlap, max_mismatches)
                if cut < len(sequence):
                    with_adapter += 1
                sequence = sequence[:cut]
                quality = quality[:cut]
                kept.append((header, sequence, plus, quality))
                bases_out += len(sequence)
        except ValueError as exc:
            raise StepError(f'fastq_adapter_trim: {exc}') from exc

        directory = output_directory(ctx, out_name)
        output_path = directory / f'{out_name}.fastq'
        output_bytes = write_fastq_file(str(output_path), kept)
        result_files = [result_file('trimmed_reads', str(output_path), 'fastq', 'Adapter-trimmed reads')]
        remember_native(ctx, out_name, result_files)

        stats = {
            'reads_in': reads_in,
            'reads_with_adapter': with_adapter,
            'reads_out': len(kept),
            'bases_in': bases_in,
            'bases_out': bases_out,
            'bases_trimmed': bases_in - bases_out,
            'mean_length_in': (bases_in / reads_in) if reads_in else 0.0,
            'mean_length_out': (bases_out / len(kept)) if kept else 0.0,
            'output_bytes': output_bytes,
        }
        data = np.asarray([[float(stats[label])] for label in _LABELS], dtype=float)
        labels = {
            'statistic': {label: index for index, label in enumerate(_LABELS)},
            'value': {'value': 0},
        }
        info = {
            'source_format': inputs[0].format,
            'adapter': adapter,
            'min_overlap': min_overlap,
            'max_mismatches': max_mismatches,
            'file': str(output_path),
            'result_files': result_files,
        }
        ctx[out_name] = Form(data=data, dims=['statistic', 'value'], labels=labels, info=info)
        self._export_data = dict(stats)
        self._export_data['file'] = str(output_path)
        self._export_data['result_files'] = result_files
        print(f'[fastq_adapter_trim] in={reads_in} with_adapter={with_adapter}')

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
