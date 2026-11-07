"""Read-level summary statistics for a FASTQ/FASTQ.gz file.

Input: FileArtifact (format fastq/fq) produced by a file source.
Output: 2D Form [statistic, value] with one row per metric.

Reads are streamed, so the operator handles whole sequencing files without
loading them into memory.
"""
from __future__ import annotations

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _fastq_utils as fq


_LABELS = (
    "n_reads",
    "n_bases",
    "min_length",
    "max_length",
    "mean_length",
    "gc_fraction",
    "mean_quality",
    "q20_fraction",
    "q30_fraction",
    "n_reads_with_n",
)


class FastqStatsStep(Step):
    """Summarise read count, length, GC content and quality of a FASTQ file."""
    provider = 'operon-core'
    parameters_file = 'fastq_stats.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_stats',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'fastq_stats',
     'description': 'Read count, length, GC fraction and base quality of a FASTQ/FASTQ.gz file.',
     'category': 'Quality Control',
     'icon': 'ChartBar',
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
        return max(int(size * 0.1), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError("fastq_stats requires a FASTQ file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("fastq", "fq"):
            raise StepError(f"fastq_stats requires a FASTQ file, got {artifact.format!r}")

        params = dict(ctx.step_params)
        max_reads = int(params.get("max_reads") or 0)
        out_name = params.get("output") or self.name
        path = next(iter(artifact.files.values()))

        n_reads = 0
        n_bases = 0
        min_length = 0
        max_length = 0
        gc_bases = 0
        qual_sum = 0.0
        qual_n = 0
        q20 = 0
        q30 = 0
        with_n = 0

        with fq.open_text(path) as stream:
            for _name, sequence, quality in fq.iter_fastq(stream, max_reads=max_reads):
                length = len(sequence)
                n_reads += 1
                n_bases += length
                min_length = length if n_reads == 1 else min(min_length, length)
                max_length = max(max_length, length)
                gc_bases += sequence.count(b"G") + sequence.count(b"C")
                if b"N" in sequence:
                    with_n += 1
                for score in fq.quality_scores(quality):
                    qual_sum += score
                    qual_n += 1
                    if score >= 20:
                        q20 += 1
                    if score >= 30:
                        q30 += 1

        values = {
            "n_reads": float(n_reads),
            "n_bases": float(n_bases),
            "min_length": float(min_length),
            "max_length": float(max_length),
            "mean_length": (n_bases / n_reads) if n_reads else 0.0,
            "gc_fraction": (gc_bases / n_bases) if n_bases else 0.0,
            "mean_quality": (qual_sum / qual_n) if qual_n else 0.0,
            "q20_fraction": (q20 / qual_n) if qual_n else 0.0,
            "q30_fraction": (q30 / qual_n) if qual_n else 0.0,
            "n_reads_with_n": float(with_n),
        }

        import numpy as np
        data = np.asarray([[values[label]] for label in _LABELS], dtype=float)
        labels = {
            "statistic": {label: index for index, label in enumerate(_LABELS)},
            "value": {"value": 0},
        }
        info = {"source_format": artifact.format, "n_reads": n_reads, "max_reads": max_reads}
        ctx[out_name] = Form(data=data, dims=["statistic", "value"], labels=labels, info=info)
        self._export_data = values
        print(f"[fastq_stats] {n_reads} reads, {n_bases} bases, mean quality {values['mean_quality']:.2f}")

    def export(self, ctx):
        return self._export_data
