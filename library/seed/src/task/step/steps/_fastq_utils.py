"""Streaming helpers shared by the FASTQ operators."""
from __future__ import annotations

import bz2
import gzip
import lzma
from pathlib import Path


def open_text(path):
    """Open a FASTQ file (optionally compressed) as a binary stream."""
    suffix = Path(path).suffix.lower()
    if suffix == ".gz":
        return gzip.open(path, "rb")
    if suffix == ".bz2":
        return bz2.open(path, "rb")
    if suffix == ".xz":
        return lzma.open(path, "rb")
    return open(path, "rb")


def iter_fastq(stream, max_reads: int = 0, chunk: int = 1 << 20):
    """Yield ``(name, sequence, quality)`` for each FASTQ record.

    ``max_reads`` of zero means no limit.  The parser reads fixed four-line
    records and tolerates a trailing blank line, but a truncated record raises
    ``ValueError`` so callers can report a precise error.
    """
    produced = 0
    while True:
        header = stream.readline()
        if not header:
            return
        header = header.strip()
        if not header:
            continue
        sequence = stream.readline().strip()
        plus = stream.readline()
        quality = stream.readline().rstrip(b"\r\n")
        if not sequence or not plus or not quality:
            raise ValueError("truncated FASTQ record near %r" % header[:60])
        if not plus.startswith(b"+"):
            raise ValueError("missing '+' separator after %r" % header[:60])
        if len(quality) != len(sequence):
            raise ValueError(
                "quality length %d does not match sequence length %d for %r"
                % (len(quality), len(sequence), header[:60])
            )
        name = header[1:].split(None, 1)[0].decode("ascii", "replace")
        yield name, sequence.upper(), quality
        produced += 1
        if max_reads and produced >= max_reads:
            return


def quality_scores(quality: bytes, offset: int = 33):
    """Return Phred scores as a small list of ints."""
    return [base - offset for base in quality]
