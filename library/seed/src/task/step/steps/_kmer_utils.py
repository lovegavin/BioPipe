# src/task/step/steps/_kmer_utils.py
"""Canonical k-mer helpers shared by the genome k-mer operators."""
from __future__ import annotations

import math

import numpy as np

from src.core import StepError
from ._annotation_utils import fasta_sequences

_CODE = np.full(256, 4, dtype=np.uint8)
for _value, _base in enumerate("ACGT"):
    _CODE[ord(_base)] = _value
    _CODE[ord(_base.lower())] = _value


def canonical_kmers(sequence, k):
    """Return canonical (min of forward/reverse-complement) k-mers as uint64."""
    if k < 1 or k > 31:
        raise StepError("k must be between 1 and 31")
    sequence = str(sequence).upper()
    raw = np.frombuffer(sequence.encode("ascii", "replace"), dtype=np.uint8)
    if raw.size < k:
        return np.empty(0, dtype=np.uint64)
    codes = _CODE[raw]
    n = raw.size - k + 1
    forward = np.zeros(n, dtype=np.uint64)
    reverse = np.zeros(n, dtype=np.uint64)
    valid = np.ones(n, dtype=bool)
    two = np.uint64(2)
    for offset in range(k):
        column = codes[offset: offset + n].astype(np.uint64)
        forward = (forward << two) | column
        valid &= column < np.uint64(4)
    for offset in range(k):
        column = codes[k - 1 - offset: k - 1 - offset + n].astype(np.uint64)
        complement = np.where(column < np.uint64(4), np.uint64(3) - column, np.uint64(0))
        reverse = (reverse << two) | complement
    canonical = np.minimum(forward, reverse)
    return canonical[valid]


def kmer_array(form, sequence_dim, position_dim, k, operator):
    names, sequences = fasta_sequences(form, sequence_dim, position_dim, operator)
    if not sequences:
        raise StepError(f"{operator}: FASTA input has no sequences")
    parts = [canonical_kmers(sequence, k) for sequence in sequences]
    parts = [part for part in parts if part.size]
    if not parts:
        raise StepError(f"{operator}: sequences shorter than k={k}")
    return names, np.concatenate(parts)


def unique_kmers(form, sequence_dim, position_dim, k, operator):
    names, values = kmer_array(form, sequence_dim, position_dim, k, operator)
    return names, np.unique(values)


def mash_distance(jaccard, k):
    """Mash distance from an exact k-mer Jaccard index."""
    j = float(min(max(jaccard, 0.0), 1.0))
    if j <= 0.0:
        return float("inf")
    distance = -math.log(2.0 * j / (1.0 + j)) / float(k)
    return max(distance, 0.0)


def spectrum_histogram(values, max_frequency):
    """Histogram of k-mer multiplicities, capped at ``max_frequency``."""
    if values.size == 0:
        return {}, 0
    _, counts = np.unique(values, return_counts=True)
    distinct = int(counts.size)
    histogram = {}
    for count in counts.astype(np.int64):
        bucket = int(count) if int(count) <= max_frequency else max_frequency + 1
        histogram[bucket] = histogram.get(bucket, 0) + 1
    return histogram, distinct
