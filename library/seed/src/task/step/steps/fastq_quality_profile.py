"""Per-position mean base quality of a FASTQ/FASTQ.gz file.

Input: FileArtifact (format fastq/fq).
Output: 2D Form [position, mean_quality], one row per cycle.

Only the first ``max_positions`` cycles are reported (zero means all cycles
seen in the file).  Reads shorter than a cycle do not contribute to it.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _fastq_utils as fq


class FastqQualityProfileStep(Step):
    """Compute the mean Phred quality at each sequencing cycle."""
    provider = 'operon-core'
    parameters_file = 'fastq_quality_profile.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_quality_profile',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'fastq_quality_profile',
     'description': 'Per-cycle mean base quality of a FASTQ/FASTQ.gz file.',
     'category': 'Quality Control',
     'icon': 'ChartLine',
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
            raise StepError("fastq_quality_profile requires a FASTQ file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("fastq", "fq"):
            raise StepError(
                f"fastq_quality_profile requires a FASTQ file, got {artifact.format!r}"
            )

        params = dict(ctx.step_params)
        max_reads = int(params.get("max_reads") or 0)
        max_positions = int(params.get("max_positions") or 0)
        out_name = params.get("output") or self.name
        path = next(iter(artifact.files.values()))

        sums: list[float] = []
        counts: list[int] = []
        n_reads = 0
        with fq.open_text(path) as stream:
            for _name, _sequence, quality in fq.iter_fastq(stream, max_reads=max_reads):
                n_reads += 1
                scores = fq.quality_scores(quality)
                if max_positions:
                    scores = scores[:max_positions]
                if len(scores) > len(sums):
                    sums.extend([0.0] * (len(scores) - len(sums)))
                    counts.extend([0] * (len(scores) - len(counts)))
                for index, score in enumerate(scores):
                    sums[index] += score
                    counts[index] += 1

        if not n_reads:
            raise StepError("fastq_quality_profile: FASTQ file contains no reads")
        means = np.asarray(
            [sums[index] / counts[index] if counts[index] else np.nan for index in range(len(sums))],
            dtype=float,
        ).reshape(-1, 1)
        positions = [str(index + 1) for index in range(len(sums))]
        labels = {
            "position": {position: index for index, position in enumerate(positions)},
            "mean_quality": {"mean_quality": 0},
        }
        info = {
            "source_format": artifact.format,
            "n_reads": n_reads,
            "max_positions": max_positions,
        }
        ctx[out_name] = Form(
            data=means, dims=["position", "mean_quality"], labels=labels, info=info
        )
        self._export_data = {
            "n_reads": n_reads,
            "n_positions": len(sums),
            "mean_quality": float(np.nanmean(means)) if len(sums) else 0.0,
            "first_position_mean": float(means[0, 0]),
            "last_position_mean": float(means[-1, 0]),
        }
        print(f"[fastq_quality_profile] {n_reads} reads x {len(sums)} cycles")

    def export(self, ctx):
        return self._export_data
