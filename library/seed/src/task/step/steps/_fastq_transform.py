"""Streaming FASTQ helpers for read-preprocessing operators.

Quality trimming follows the BWA algorithm used by cutadapt: walk the read
from the 3' end while the running score of ``cutoff - quality`` keeps rising,
then cut at the best-scoring position.  Adapter trimming is a no-indel,
leftmost exact match followed by the longest 3' partial match, which matches
``cutadapt --no-indels -e 0`` for the same parameters.
"""
from __future__ import annotations

import gzip
from pathlib import Path

from src.core import FileArtifact, StepError


def fastq_path(artifact, operator: str) -> str:
    """Validate a FASTQ FileArtifact and return its path."""
    if not isinstance(artifact, FileArtifact) or artifact.format not in ("fastq", "fq"):
        raise StepError(f"{operator} requires a FASTQ file artifact")
    artifact.validate()
    return next(iter(artifact.files.values()))


def read_fastq(path: str):
    """Yield (header, sequence, plus, quality) for a plain or gzipped FASTQ."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
        index = 0
        while True:
            header = handle.readline()
            if not header:
                return
            header = header.rstrip("\r\n")
            sequence = handle.readline().strip()
            plus = handle.readline().rstrip("\r\n") or "+"
            quality = handle.readline().rstrip("\r\n")
            index += 1
            if not sequence or len(sequence) != len(quality):
                raise StepError(
                    f"malformed FASTQ record {index}: sequence and quality lengths differ"
                )
            yield header, sequence.upper(), plus, quality


def write_fastq(path: str, records) -> int:
    """Write records as LF-terminated FASTQ and return the byte count."""
    chunks = []
    for header, sequence, plus, quality in records:
        chunks.append(f"{header}\n{sequence}\n{plus}\n{quality}\n")
    payload = "".join(chunks).encode("utf-8")
    target = Path(path)
    target.write_bytes(payload)
    return len(payload)


def quality_trim_index(quality: str, cutoff: int) -> int:
    """Return the read length after cutadapt-style 3' quality trimming."""
    total = 0
    best = 0
    cut = len(quality)
    for index in range(len(quality) - 1, -1, -1):
        total += cutoff - (ord(quality[index]) - 33)
        if total < 0:
            break
        if total > best:
            best = total
            cut = index
    return cut


def adapter_trim_index(sequence: str, adapter: str, min_overlap: int = 3,
                       max_mismatches: int = 0) -> int:
    """Return the read length after removing a 3' adapter (no indels)."""
    adapter = adapter.upper()
    if not adapter:
        return len(sequence)
    position = sequence.find(adapter)
    if position >= 0:
        return position
    limit = min(len(adapter), len(sequence))
    for overlap in range(limit, min_overlap - 1, -1):
        mismatches = sum(
            1 for left, right in zip(sequence[-overlap:], adapter[:overlap]) if left != right
        )
        if mismatches <= max_mismatches:
            return len(sequence) - overlap
    return len(sequence)


_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def reverse_complement_sequence(sequence: str) -> str:
    """Return the reverse complement, leaving other symbols unchanged."""
    return sequence.translate(_COMPLEMENT)[::-1]


def deduplicate(records, collapse_reverse_complements: bool = False):
    """Collapse identical sequences, keeping the first record and its order.

    When ``collapse_reverse_complements`` is true a read whose sequence is the
    reverse complement of an earlier read counts as a duplicate, matching the
    default ``seqkit rmdup`` behavior.
    """
    order = []
    counts = {}
    for record in records:
        sequence = record[1]
        key = sequence
        if collapse_reverse_complements:
            reverse = reverse_complement_sequence(sequence)
            key = sequence if sequence <= reverse else reverse
        if key in counts:
            counts[key] += 1
            continue
        counts[key] = 1
        order.append(record)
    return order, counts


def write_fastq_file(path: str, records) -> int:
    return write_fastq(path, records)
