"""Summarise BAM alignment flags in the style of ``samtools flagstat``.

Input: FileArtifact (format bam).
Output: 2D Form [statistic, value] with the same counters samtools flagstat
prints (counts only, no percentages).

The reader parses the BAM record header fields directly and never decodes
sequences or qualities, so memory stays constant for large files.
"""
from __future__ import annotations

import gzip
import struct

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_LABELS = (
    "total",
    "primary",
    "secondary",
    "supplementary",
    "duplicates",
    "primary_duplicates",
    "mapped",
    "primary_mapped",
    "paired_in_sequencing",
    "read1",
    "read2",
    "properly_paired",
    "with_itself_and_mate_mapped",
    "singletons",
    "mate_mapped_to_different_chr",
    "mate_mapped_to_different_chr_mapq5",
)

_FLAG_PAIRED = 0x1
_FLAG_PROPER_PAIR = 0x2
_FLAG_UNMAPPED = 0x4
_FLAG_MATE_UNMAPPED = 0x8
_FLAG_READ1 = 0x40
_FLAG_READ2 = 0x80
_FLAG_SECONDARY = 0x100
_FLAG_DUPLICATE = 0x400
_FLAG_SUPPLEMENTARY = 0x800

_MAGIC = b"BAM\x01"


def _is_gzip(path: str) -> bool:
    with open(path, "rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def iter_bam_records(path: str, max_records: int = 0):
    """Yield raw BAM record blocks (without the 4-byte block size)."""
    opener = gzip.open if _is_gzip(path) else open
    with opener(path, "rb") as handle:
        if handle.read(4) != _MAGIC:
            raise ValueError("not a BAM file (missing BAM\\x01 magic)")
        (l_text,) = struct.unpack("<i", handle.read(4))
        handle.read(l_text)
        (n_ref,) = struct.unpack("<i", handle.read(4))
        for _ in range(n_ref):
            (l_name,) = struct.unpack("<i", handle.read(4))
            handle.read(l_name)
            handle.read(4)
        seen = 0
        while True:
            head = handle.read(4)
            if len(head) < 4:
                break
            (block_size,) = struct.unpack("<i", head)
            record = handle.read(block_size)
            if len(record) < block_size:
                raise ValueError("truncated BAM record")
            yield record
            seen += 1
            if max_records and seen >= max_records:
                break


def flagstat_counts(records) -> dict:
    counts = {label: 0 for label in _LABELS}
    for record in records:
        (flag,) = struct.unpack_from("<H", record, 14)
        mapq = record[9]
        (ref_id,) = struct.unpack_from("<i", record, 0)
        (next_ref_id,) = struct.unpack_from("<i", record, 20)

        counts["total"] += 1
        secondary = bool(flag & _FLAG_SECONDARY)
        supplementary = bool(flag & _FLAG_SUPPLEMENTARY)
        duplicate = bool(flag & _FLAG_DUPLICATE)
        unmapped = bool(flag & _FLAG_UNMAPPED)
        paired = bool(flag & _FLAG_PAIRED)
        mate_unmapped = bool(flag & _FLAG_MATE_UNMAPPED)
        primary = not secondary and not supplementary

        if secondary:
            counts["secondary"] += 1
        if supplementary:
            counts["supplementary"] += 1
        if duplicate:
            counts["duplicates"] += 1
        if primary:
            counts["primary"] += 1
            if duplicate:
                counts["primary_duplicates"] += 1
        if not unmapped:
            counts["mapped"] += 1
            if primary:
                counts["primary_mapped"] += 1
        if paired:
            counts["paired_in_sequencing"] += 1
        if flag & _FLAG_READ1:
            counts["read1"] += 1
        if flag & _FLAG_READ2:
            counts["read2"] += 1
        if flag & _FLAG_PROPER_PAIR:
            counts["properly_paired"] += 1
        both_mapped = paired and not unmapped and not mate_unmapped
        if both_mapped:
            counts["with_itself_and_mate_mapped"] += 1
        if paired and not unmapped and mate_unmapped:
            counts["singletons"] += 1
        if both_mapped and next_ref_id != ref_id:
            counts["mate_mapped_to_different_chr"] += 1
            if mapq >= 5:
                counts["mate_mapped_to_different_chr_mapq5"] += 1
    return counts


class BamFlagstatStep(Step):
    """Count BAM flag categories compatible with samtools flagstat."""
    provider = 'operon-core'
    parameters_file = 'bam_flagstat.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bam_flagstat',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'bam_flagstat',
     'description': 'Summarise BAM alignment flags like samtools flagstat (counts only).',
     'category': 'Quality Control',
     'icon': 'ListChecks',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'kind': 'file',
                               'numeric': False,
                               'ndim': 0,
                               'dims': [],
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['bam']}}}],
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
        return max(int(size * 0.05), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], FileArtifact):
            raise StepError("bam_flagstat requires a BAM file artifact")
        artifact = inputs[0]
        artifact.validate()
        if artifact.format != "bam":
            raise StepError(f"bam_flagstat requires a BAM file, got {artifact.format!r}")
        params = dict(ctx.step_params)
        max_records = int(params.get("max_records") or 0)
        out_name = params.get("output") or self.name
        path = next(iter(artifact.files.values()))

        try:
            counts = flagstat_counts(iter_bam_records(path, max_records=max_records))
        except ValueError as exc:
            raise StepError(f"bam_flagstat: {exc}") from exc

        data = np.asarray([[float(counts[label])] for label in _LABELS], dtype=float)
        labels = {
            "statistic": {label: index for index, label in enumerate(_LABELS)},
            "value": {"value": 0},
        }
        info = {"source_format": artifact.format, "max_records": max_records}
        ctx[out_name] = Form(data=data, dims=["statistic", "value"], labels=labels, info=info)
        self._export_data = dict(counts)
        print(
            f"[bam_flagstat] total={counts['total']} mapped={counts['mapped']} "
            f"properly_paired={counts['properly_paired']}"
        )

    def export(self, ctx):
        return self._export_data
