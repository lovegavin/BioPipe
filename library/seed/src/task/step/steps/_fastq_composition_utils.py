"""Helpers for FASTQ composition QC (duplication, over-representation, GC)."""
from __future__ import annotations

import gzip
from collections import Counter

import numpy as np

from src.core import FileArtifact, StepError


LEVELS = (
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4", 4, 4),
    ("5", 5, 5),
    ("6", 6, 6),
    ("7", 7, 7),
    ("8", 8, 8),
    ("9", 9, 9),
    (">10", 10, 49),
    (">50", 50, 99),
    (">100", 100, 499),
    (">500", 500, 999),
    (">1k", 1000, 9999),
    (">10k+", 10000, 10**12),
)


def fastq_path(artifact, operator):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} requires a FASTQ file artifact")
    artifact.validate()
    if artifact.format not in ("fastq", "fq"):
        raise StepError(f"{operator} requires a FASTQ file, got {artifact.format!r}")
    return next(iter(artifact.files.values()))


def iter_sequences(path, max_reads=0):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        yielded = 0
        for index, line in enumerate(handle):
            if index % 4 != 1:
                continue
            sequence = line.strip().upper()
            if not sequence:
                raise StepError(f"fastq: empty sequence at read {yielded + 1}")
            yield sequence
            yielded += 1
            if max_reads and yielded >= max_reads:
                break


def duplication_counts(path, max_reads=0):
    counts = Counter(iter_sequences(path, max_reads))
    total = sum(counts.values())
    if not total:
        raise StepError("fastq_duplication_profile: no reads found")
    return counts, Counter(counts.values()), total


def duplication_rows(counts, levels, total):
    unique = len(counts)
    rows = []
    for label, low, high in LEVELS:
        n = sum(v for k, v in levels.items() if low <= k <= high)
        rows.append((label, n, n / total, n / unique if unique else 0.0))
    return rows, unique


def gc_percent(sequence):
    gc = sequence.count("G") + sequence.count("C")
    return int(round(gc * 100.0 / len(sequence)))


def gc_histogram(path, max_reads=0):
    histogram = np.zeros(101, dtype=np.int64)
    total = 0
    for sequence in iter_sequences(path, max_reads):
        histogram[gc_percent(sequence)] += 1
        total += 1
    if not total:
        raise StepError("fastq_gc_distribution: no reads found")
    return histogram, total
