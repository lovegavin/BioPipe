"""Sequence duplication profile of a FASTQ file (FastQC-style levels)."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._fastq_composition_utils import duplication_counts, duplication_rows, fastq_path


class FastqDuplicationProfileStep(Step):
    provider = 'operon-core'
    parameters_file = 'fastq_duplication_profile.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_duplication_profile',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'fastq_duplication_profile',
     'description': 'Histogram of read duplication levels with deduplicated percentage.',
     'category': 'Quality Control',
     'icon': 'Copy',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'kind': 'file',
                               'numeric': False,
                               'ndim': 0,
                               'dims': [],
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['fastq', 'fq']}}}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "file_bytes", 0) or 0) for item in inputs or [])
        return max(int(size * 4), 32 * 1024**2), 256 * 1024

    def run(self, ctx: Context, inputs) -> None:
        artifact = inputs[0] if inputs else None
        path = fastq_path(artifact, "fastq_duplication_profile")
        params = dict(ctx.step_params)
        max_reads = int(params.get("max_reads") or 0)
        out_name = params.get("output") or self.name
        counts, levels, total = duplication_counts(path, max_reads)
        rows, unique = duplication_rows(counts, levels, total)
        data = np.asarray([[float(row[1]), row[2], row[3]] for row in rows], dtype=float)
        labels = {
            "level": {row[0]: index for index, row in enumerate(rows)},
            "statistic": {"n_sequences": 0, "fraction_total": 1, "fraction_unique": 2},
        }
        info = {
            "total_reads": total,
            "unique_sequences": unique,
            "deduplicated_percentage": unique / total * 100.0,
            "max_reads": max_reads,
        }
        ctx[out_name] = Form(data=data, dims=["level", "statistic"], labels=labels, info=info)
        self._export_data = {
            "total_reads": total,
            "unique_sequences": unique,
            "deduplicated_percentage": unique / total * 100.0,
        }
        print(f"[fastq_duplication_profile] total={total} unique={unique}")

    def export(self, ctx):
        return self._export_data
