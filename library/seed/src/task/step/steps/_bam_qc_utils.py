"""Helpers for BAM alignment quality-control operators.

Records are streamed with :func:`_bam_utils.iter_records`; nothing here
materializes read sequences or qualities.  CIGAR operations are used to
recover query length and clipping because the record helper deliberately
keeps its payload small.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._bam_utils import iter_records, read_header

_QUERY_OPS = frozenset("MIS=X")


def bam_path(artifact, operator: str) -> str:
    """Return the path of a BAM ``FileArtifact`` after contract checks."""
    if getattr(artifact, "format", None) != "bam":
        raise StepError(f"{operator}: expected a BAM file artifact")
    artifact.validate()
    files = list(artifact.files.values())
    if not files:
        raise StepError(f"{operator}: BAM artifact has no file")
    return str(files[0])


def query_length(record) -> int:
    """Length of the read on the query axis (M/I/S/=/X operations)."""
    return sum(length for op, length in record["cigar"] if op in _QUERY_OPS)


def _primary_mapped(flag: int) -> bool:
    return not (flag & 0x4) and not (flag & 0x100) and not (flag & 0x800)


def mapq_histogram(path: str, max_mapq: int = 60, max_records: int = 0):
    """Histogram of MAPQ values for primary mapped reads (values clamped)."""
    counts = np.zeros(max_mapq + 1, dtype=np.int64)
    n_reads = 0
    total_mapq = 0
    for record in iter_records(path, max_records):
        flag = record["flag"]
        if not _primary_mapped(flag):
            continue
        value = min(int(record["mapq"]), max_mapq)
        counts[value] += 1
        n_reads += 1
        total_mapq += value
    return counts, n_reads, total_mapq


def median_from_histogram(counts, total: int) -> float:
    if total <= 0:
        return 0.0
    cumulative = np.cumsum(counts)
    index = int(np.searchsorted(cumulative, (total + 1) // 2))
    return float(index)


def read_length_histogram(path: str, max_length: int = 1000, max_records: int = 0):
    """Histogram of query lengths; longer reads land in the last bin."""
    counts = np.zeros(max_length + 1, dtype=np.int64)
    n_reads = 0
    total_bases = 0
    min_length = None
    max_seen = 0
    overflow = 0
    for record in iter_records(path, max_records):
        if not _primary_mapped(record["flag"]):
            continue
        length = query_length(record)
        if length <= 0:
            continue
        n_reads += 1
        total_bases += length
        if min_length is None or length < min_length:
            min_length = length
        if length > max_seen:
            max_seen = length
        if length > max_length:
            overflow += 1
            counts[max_length] += 1
        else:
            counts[length] += 1
    return counts, n_reads, total_bases, min_length, max_seen, overflow


def alignment_summary(path: str, max_records: int = 0) -> dict:
    """Counts and fractions used by the alignment summary operator."""
    _, references = read_header(path)
    total = mapped = primary = secondary = supplementary = 0
    duplicate = paired = proper = reverse = unmapped = 0
    clipped_reads = 0
    clipped_bases = 0
    mapq_sum = 0
    for record in iter_records(path, max_records):
        flag = record["flag"]
        total += 1
        is_secondary = bool(flag & 0x100)
        is_supplementary = bool(flag & 0x800)
        secondary += int(is_secondary)
        supplementary += int(is_supplementary)
        if flag & 0x4:
            unmapped += 1
            continue
        mapped += 1
        if is_secondary or is_supplementary:
            continue
        primary += 1
        duplicate += int(bool(flag & 0x400))
        paired += int(bool(flag & 0x1))
        proper += int(bool(flag & 0x2))
        reverse += int(bool(flag & 0x10))
        mapq_sum += min(int(record["mapq"]), 60)
        soft = sum(length for op, length in record["cigar"] if op in "SH")
        if soft:
            clipped_reads += 1
            clipped_bases += soft
    return {
        "total_reads": total,
        "mapped_reads": mapped,
        "unmapped_reads": unmapped,
        "primary_reads": primary,
        "secondary_reads": secondary,
        "supplementary_reads": supplementary,
        "duplicate_reads": duplicate,
        "paired_reads": paired,
        "proper_pair_reads": proper,
        "reverse_reads": reverse,
        "clipped_reads": clipped_reads,
        "clipped_bases": clipped_bases,
        "mapq_sum": mapq_sum,
        "references": len(references),
    }


def summarize(summary: dict) -> dict:
    """Derive fractions from raw counts."""
    total = max(summary["total_reads"], 1)
    paired = max(summary["paired_reads"], 1)
    primary = max(summary["primary_reads"], 1)
    return {
        "total_reads": summary["total_reads"],
        "mapped_reads": summary["mapped_reads"],
        "mapped_fraction": summary["mapped_reads"] / total,
        "unmapped_reads": summary["unmapped_reads"],
        "primary_reads": summary["primary_reads"],
        "secondary_reads": summary["secondary_reads"],
        "supplementary_reads": summary["supplementary_reads"],
        "duplicate_reads": summary["duplicate_reads"],
        "duplicate_fraction": summary["duplicate_reads"] / primary,
        "paired_reads": summary["paired_reads"],
        "proper_pair_fraction": summary["proper_pair_reads"] / paired,
        "reverse_fraction": summary["reverse_reads"] / primary,
        "clipped_fraction": summary["clipped_reads"] / primary,
        "mean_mapq": summary["mapq_sum"] / primary,
        "clipped_bases_per_read": summary["clipped_bases"] / primary,
        "references": summary["references"],
    }
