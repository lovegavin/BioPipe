"""Collapse duplicate FASTQ reads by sequence, keeping the first occurrence."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._fastq_transform import (
    deduplicate,
    fastq_path,
    read_fastq,
    write_fastq_file,
)
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_LABELS = (
    "reads_in",
    "reads_unique",
    "reads_duplicate",
    "duplicate_fraction",
    "bases_in",
    "bases_out",
    "mean_length",
    "output_bytes",
)


class FastqDeduplicateStep(Step):
    """Remove duplicate sequences while preserving the original order."""

    provider = 'operon-core'
    parameters_file = 'fastq_deduplicate.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'fastq_deduplicate',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'fastq_deduplicate',
        'description': 'Collapse duplicate sequences, keeping the first read and its order.',
        'category': 'Quality Control',
        'icon': 'Layers',
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
            raise StepError('fastq_deduplicate requires a FASTQ file artifact')
        path = fastq_path(inputs[0], 'fastq_deduplicate')
        params = dict(ctx.step_params)
        max_records = int(params.get('max_records') or 0)
        collapse = bool(params.get('collapse_reverse_complements') or False)
        out_name = params.get('output') or self.name

        records = []
        bases_in = 0
        try:
            for record in read_fastq(path):
                records.append(record)
                bases_in += len(record[1])
                if max_records and len(records) >= max_records:
                    break
        except ValueError as exc:
            raise StepError(f'fastq_deduplicate: {exc}') from exc

        unique, counts = deduplicate(records, collapse)
        directory = output_directory(ctx, out_name)
        output_path = directory / f'{out_name}.fastq'
        output_bytes = write_fastq_file(str(output_path), unique)
        result_files = [result_file('unique_reads', str(output_path), 'fastq', 'Deduplicated reads')]
        remember_native(ctx, out_name, result_files)

        reads_in = len(records)
        reads_unique = len(unique)
        bases_out = sum(len(record[1]) for record in unique)
        stats = {
            'reads_in': reads_in,
            'reads_unique': reads_unique,
            'reads_duplicate': reads_in - reads_unique,
            'duplicate_fraction': ((reads_in - reads_unique) / reads_in) if reads_in else 0.0,
            'bases_in': bases_in,
            'bases_out': bases_out,
            'mean_length': (bases_out / reads_unique) if reads_unique else 0.0,
            'output_bytes': output_bytes,
        }
        data = np.asarray([[float(stats[label])] for label in _LABELS], dtype=float)
        labels = {
            'statistic': {label: index for index, label in enumerate(_LABELS)},
            'value': {'value': 0},
        }
        info = {
            'source_format': inputs[0].format,
            'max_records': max_records,
            'collapse_reverse_complements': collapse,
            'file': str(output_path),
            'result_files': result_files,
        }
        ctx[out_name] = Form(data=data, dims=['statistic', 'value'], labels=labels, info=info)
        self._export_data = dict(stats)
        self._export_data['file'] = str(output_path)
        self._export_data['result_files'] = result_files
        print(f'[fastq_deduplicate] in={reads_in} unique={reads_unique}')

    def export(self, ctx):
        return dict(getattr(self, '_export_data', {}))
