"""Per-read GC content distribution of a FASTQ file."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._fastq_composition_utils import fastq_path, gc_histogram


class FastqGcDistributionStep(Step):
    provider = 'operon-core'
    parameters_file = 'fastq_gc_distribution.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_gc_distribution',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'fastq_gc_distribution',
     'description': 'Histogram of per-read GC percentages with summary statistics.',
     'category': 'Quality Control',
     'icon': 'BarChart3',
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
        return max(int(size * 2), 16 * 1024**2), 128 * 1024

    def run(self, ctx: Context, inputs) -> None:
        artifact = inputs[0] if inputs else None
        path = fastq_path(artifact, "fastq_gc_distribution")
        params = dict(ctx.step_params)
        max_reads = int(params.get("max_reads") or 0)
        out_name = params.get("output") or self.name
        histogram, total = gc_histogram(path, max_reads)
        data = np.asarray([[float(histogram[i]), float(histogram[i]) / total] for i in range(101)], dtype=float)
        weights = np.repeat(np.arange(101, dtype=float), histogram)
        mean = float(weights.mean())
        median = float(np.median(weights))
        stdev = float(weights.std(ddof=0))
        mode = int(np.argmax(histogram))
        labels = {
            "gc_percent": {str(i): i for i in range(101)},
            "statistic": {"n_reads": 0, "fraction": 1},
        }
        info = {"total_reads": total, "mean_gc": mean, "median_gc": median,
                "stdev_gc": stdev, "mode_gc": mode, "max_reads": max_reads}
        ctx[out_name] = Form(data=data, dims=["gc_percent", "statistic"], labels=labels, info=info)
        self._export_data = {"total_reads": total, "mean_gc": mean, "median_gc": median,
                             "stdev_gc": stdev, "mode_gc": mode}
        print(f"[fastq_gc_distribution] total={total} mean={mean:.2f}")

    def export(self, ctx):
        return self._export_data
