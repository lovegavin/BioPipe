"""Scan FASTQ reads for common sequencing adapters.

Input: FileArtifact (format fastq/fq).
Output: 2D Form [adapter, metric] with ``reads_with_adapter`` and
``fraction`` columns for each configured adapter.

A read counts for an adapter when a prefix of the adapter (at least
``min_overlap`` bases) aligns to the read at any offset with at most
``max_mismatches`` substitutions.  Each read is counted at most once per
adapter.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _fastq_utils as fq


_DEFAULT_ADAPTERS = (
    ("illumina", "AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC"),
    ("nextera", "CTGTCTCTTATACACATCT"),
    ("small_rna", "TGGAATTCTCGGGTGCCAAGG"),
)

_METRICS = ("reads_with_adapter", "fraction")


def parse_adapters(text: str):
    """Parse ``name:SEQ,name:SEQ`` or return the default adapter panel."""
    text = (text or "").strip()
    if not text:
        return list(_DEFAULT_ADAPTERS)
    panel = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"adapter entry {item!r} must be name:SEQUENCE")
        name, sequence = item.split(":", 1)
        sequence = sequence.strip().upper()
        if not name.strip() or not sequence:
            raise ValueError(f"adapter entry {item!r} is incomplete")
        panel.append((name.strip(), sequence))
    if not panel:
        raise ValueError("adapter panel is empty")
    return panel


def _exact_prefix_present(read: bytes, adapter: bytes, min_overlap: int) -> bool:
    limit = min(len(adapter), len(read))
    for overlap in range(limit, min_overlap - 1, -1):
        if read[-overlap:] == adapter[:overlap]:
            return True
    return False


def _approx_prefix_present(
    read: bytes, adapter: bytes, min_overlap: int, max_mismatches: int
) -> bool:
    limit = min(len(adapter), len(read))
    for overlap in range(limit, min_overlap - 1, -1):
        mismatches = 0
        for left, right in zip(read[-overlap:], adapter[:overlap]):
            if left != right:
                mismatches += 1
                if mismatches > max_mismatches:
                    break
        if mismatches <= max_mismatches:
            return True
    return False


class FastqAdapterScanStep(Step):
    """Count reads containing Illumina, Nextera or custom adapter prefixes."""
    provider = 'operon-core'
    parameters_file = 'fastq_adapter_scan.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fastq_adapter_scan',
     'version': '1.0.1',
     'kind': 'operator',
     'title': 'fastq_adapter_scan',
     'description': 'Count reads containing known sequencing adapter prefixes.',
     'category': 'Quality Control',
     'icon': 'MagnifyingGlass',
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
            raise StepError("fastq_adapter_scan requires a FASTQ file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ("fastq", "fq"):
            raise StepError(
                f"fastq_adapter_scan requires a FASTQ file, got {artifact.format!r}"
            )

        params = dict(ctx.step_params)
        max_reads = int(params.get("max_reads") or 0)
        min_overlap = int(params.get("min_overlap") or 8)
        max_mismatches = int(params.get("max_mismatches") or 0)
        if min_overlap < 1:
            raise StepError("fastq_adapter_scan: min_overlap must be positive")
        if max_mismatches < 0:
            raise StepError("fastq_adapter_scan: max_mismatches must be non-negative")
        try:
            panel = parse_adapters(str(params.get("adapters") or ""))
        except ValueError as exc:
            raise StepError(f"fastq_adapter_scan: {exc}") from exc
        out_name = params.get("output") or self.name
        path = next(iter(artifact.files.values()))

        counts = {name: 0 for name, _sequence in panel}
        n_reads = 0
        with fq.open_text(path) as stream:
            for _read_name, sequence, _quality in fq.iter_fastq(stream, max_reads=max_reads):
                n_reads += 1
                for name, adapter in panel:
                    motif = adapter.encode("ascii")
                    if max_mismatches:
                        hit = _approx_prefix_present(sequence, motif, min_overlap, max_mismatches)
                    else:
                        hit = _exact_prefix_present(sequence, motif, min_overlap)
                    if hit:
                        counts[name] += 1

        data = np.asarray(
            [[counts[name], (counts[name] / n_reads if n_reads else 0.0)] for name, _ in panel],
            dtype=float,
        )
        labels = {
            "adapter": {name: index for index, (name, _sequence) in enumerate(panel)},
            "metric": {metric: index for index, metric in enumerate(_METRICS)},
        }
        info = {"source_format": artifact.format, "n_reads": n_reads, "adapters": [n for n, _ in panel]}
        ctx[out_name] = Form(data=data, dims=["adapter", "metric"], labels=labels, info=info)
        self._export_data = {
            "n_reads": n_reads,
            "adapters": {name: counts[name] for name, _ in panel},
            "fractions": {name: (counts[name] / n_reads if n_reads else 0.0) for name, _ in panel},
        }
        print(f"[fastq_adapter_scan] {n_reads} reads, " + ", ".join(f"{n}={c}" for n, c in counts.items()))

    def export(self, ctx):
        return self._export_data
