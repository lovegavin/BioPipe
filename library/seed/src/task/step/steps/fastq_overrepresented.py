"""Sequences over-represented beyond a fraction of the FASTQ library."""
from __future__ import annotations

from collections import Counter

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._fastq_composition_utils import fastq_path, iter_sequences


def overrepresented_rows(path, threshold, max_reads, adapters):
    counts = Counter(iter_sequences(path, max_reads))
    total = sum(counts.values())
    if not total:
        raise StepError("fastq_overrepresented: no reads found")
    rows = []
    for sequence, count in counts.most_common():
        fraction = count / total
        if fraction < threshold:
            break
        source = ""
        for adapter in adapters:
            if adapter and (adapter in sequence or sequence in adapter):
                source = "adapter"
                break
        rows.append((sequence, count, fraction, source))
    return rows, total


class FastqOverrepresentedStep(Step):
    provider = 'operon-core'
    parameters_file = 'fastq_overrepresented.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_overrepresented',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'fastq_overrepresented',
     'description': 'List sequences exceeding a fraction threshold with optional adapter source.',
     'category': 'Quality Control',
     'icon': 'AlertTriangle',
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
        path = fastq_path(artifact, "fastq_overrepresented")
        params = dict(ctx.step_params)
        threshold = float(params.get("threshold") or 0.001)
        max_reads = int(params.get("max_reads") or 0)
        adapters = [str(item) for item in (params.get("adapters") or [])]
        out_name = params.get("output") or self.name
        rows, total = overrepresented_rows(path, threshold, max_reads, adapters)
        data = np.asarray([[float(row[1]), row[2]] for row in rows], dtype=float)
        data = data.reshape((len(rows), 2))
        labels = {
            "sequence": {row[0]: index for index, row in enumerate(rows)},
            "statistic": {"n_reads": 0, "fraction_total": 1},
        }
        info = {
            "total_reads": total,
            "threshold": threshold,
            "n_overrepresented": len(rows),
            "sources": {row[0]: row[3] for row in rows if row[3]},
            "adapters": adapters,
        }
        ctx[out_name] = Form(data=data, dims=["sequence", "statistic"], labels=labels, info=info)
        self._export_data = {
            "total_reads": total,
            "n_overrepresented": len(rows),
            "threshold": threshold,
        }

    def export(self, ctx):
        return self._export_data
