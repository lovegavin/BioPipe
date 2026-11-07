"""Trim low-quality 3' ends of FASTQ reads with the cutadapt/BWA algorithm."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._fastq_transform import (
    fastq_path,
    quality_trim_index,
    read_fastq,
    write_fastq_file,
)
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_LABELS = (
    "reads_in",
    "reads_out",
    "reads_dropped",
    "bases_in",
    "bases_out",
    "bases_trimmed",
    "reads_trimmed",
    "mean_length_in",
    "mean_length_out",
    "min_quality",
    "min_length",
    "bytes_out",
)


class FastqQualityTrimStep(Step):
    """Trim the 3' end of reads while the running quality score improves."""

    provider = 'operon-core'
    parameters_file = 'fastq_quality_trim.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'fastq_quality_trim',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'fastq_quality_trim',
        'description': 'Trim low-quality 3-prime ends using the BWA/cutadapt running-score rule.',
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
            raise StepError('fastq_quality_trim requires a FASTQ file artifact')
        path = fastq_path(inputs[0], 'fastq_quality_trim')
        params = dict(ctx.step_params)
        min_quality = int(params.get('min_quality') or 20)
        min_length = int(params.get('min_length') or 0)
        max_records = int(params.get('max_records') or 0)
        if not 0 <= min_quality <= 41:
            raise StepError('fastq_quality_trim: min_quality must be within 0..41')
        if min_length < 0:
            raise StepError('fastq_quality_trim: min_length must be non-negative')
        out_name = params.get('output') or self.name

        kept = []
        reads_in = 0
        reads_dropped = 0
        reads_trimmed = 0
        bases_in = 0
        bases_out = 0
        try:
            for header, sequence, plus, quality in read_fastq(path):
                if max_records and reads_in >= max_records:
                    break
                reads_in += 1
                bases_in += len(sequence)
                cut = quality_trim_index(quality, min_quality)
                if cut < len(sequence):
                    reads_trimmed += 1
                sequence = sequence[:cut]
                quality = quality[:cut]
                if len(sequence) < min_length:
                    reads_dropped += 1
                    continue
                kept.append((header, sequence, plus, quality))
                bases_out += len(sequence)
        except ValueError as exc:
            raise StepError(f'fastq_quality_trim: {exc}') from exc

        directory = output_directory(ctx, out_name)
        output_path = directory / f'{out_name}.fastq'
        bytes_out = write_fastq_file(str(output_path), kept)
        result_files = [result_file('trimmed_reads', str(output_path), 'fastq', 'Quality-trimmed reads')]
        remember_native(ctx, out_name, result_files)

        reads_out = len(kept)
        stats = {
            'reads_in': reads_in,
            'reads_out': reads_out,
            'reads_dropped': reads_dropped,
            'bases_in': bases_in,
            'bases_out': bases_out,
            'bases_trimmed': bases_in - bases_out,
            'mean_length_in': (bases_in / reads_in) if reads_in else 0.0,
            'mean_length_out': (bases_out / reads_out) if reads_out else 0.0,
            'reads_trimmed': reads_trimmed,
            'min_quality': min_quality,
            'min_length': min_length,
            'bytes_out': bytes_out,
        }
        data = np.asarray([[float(stats[label])] for label in _LABELS], dtype=float)
        labels = {
            'statistic': {label: index for index, label in enumerate(_LABELS)},
            'value': {'value': 0},
        }
        info = {
            'source_format': inputs[0].format,
            'reads_trimmed': reads_trimmed,
            'min_quality': min_quality,
            'min_length': min_length,
            'max_records': max_records,
            'file': str(output_path),
            'result_files': result_files,
        }
        ctx[out_name] = Form(data=data, dims=['statistic', 'value'], labels=labels, info=info)
        self._export_data = dict(stats)
        self._export_data['file'] = str(output_path)
        self._export_data['result_files'] = result_files
        print(f'[fastq_quality_trim] in={reads_in} out={reads_out} dropped={reads_dropped}')

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
