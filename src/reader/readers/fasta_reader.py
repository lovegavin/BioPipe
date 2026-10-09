# src/reader/readers/fasta_reader.py
"""FASTA reader.

Parses nucleotide or protein sequences from a FASTA file.

Layout:
    axis 0 = sequence, axis 1 = position.
``dims`` names the two axes in that order.

Sequences of different lengths are padded with NaN to the maximum
length found in the file. The ``sequence`` axis is labeled with the
identifier from each description line (the first whitespace-delimited
token after ``>``).

Characters are encoded as integers:
    A=0, C=1, G=2, T=3, U=3, N=4, anything else=5.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader


# Character -> integer mapping.
_CHAR_MAP = {
    "A": 0, "C": 1, "G": 2,
    "T": 3, "U": 3,
    "N": 4,
}
_UNKNOWN = 5


class FastaReader(Reader):
    """Reader for .fasta / .fa / .fna / .faa files."""

    extensions = [".fasta", ".fa", ".fna", ".faa"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "FASTA reader expects dims as a two-element list, "
                "e.g. dims: [sequence, position]"
            )
        sequence_dim, position_dim = dims[0], dims[1]

        ids, seqs = _parse_fasta(path)
        if not ids:
            raise ReaderError("FASTA file contains no sequences")

        max_len = max(len(s) for s in seqs)
        n = len(ids)

        # Encode and pad.
        data = np.full((n, max_len), np.nan, dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = _CHAR_MAP.get(ch.upper(), _UNKNOWN)

        return Form(
            data=data,
            dims=[sequence_dim, position_dim],
            labels={
                sequence_dim: {sid: i for i, sid in enumerate(ids)},
            },
            info={"missing_code": np.nan},
        )


def _open_maybe_gz(path: Path):
    if str(path).lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _parse_fasta(path: Path) -> tuple[list[str], list[str]]:
    """Return (ids, sequences) from a FASTA file."""
    ids: list[str] = []
    seqs: list[str] = []
    current_seq: list[str] = []

    with _open_maybe_gz(path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith(">"):
                if current_seq:
                    seqs.append("".join(current_seq))
                    current_seq = []
                # ID is the first whitespace-delimited token.
                header = line[1:].strip()
                sid = header.split()[0] if header.split() else f"seq{len(ids)}"
                ids.append(sid)
            else:
                current_seq.append(line)

    if current_seq:
        seqs.append("".join(current_seq))

    return ids, seqs