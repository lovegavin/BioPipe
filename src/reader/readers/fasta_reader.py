# src/reader/readers/fasta_reader.py
"""FASTA reader.

Parses nucleotide or protein sequences.

Layout:
    axis 0 = sequence, axis 1 = position.

Sequences of different lengths are padded with NaN to the maximum
length found in the file. Characters are encoded as integers:

    A=0, C=1, G=2, T=3, U=3, N=4, anything else=5

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           sequence: first token after '>'
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto`` for position and
``builtin`` for sequence. Duplicate identifiers are disambiguated by
appending ``#<position>``.

When sequence identifiers are non-numeric they are encoded; the
encoder instance is recorded in ``info["encoders"]``.

The alphabet is inferred from the observed characters and recorded
in ``info["alphabet"]`` as one of ``"dna"``, ``"rna"`` or
``"protein"``.

Reference
---------
FASTA format:
https://en.wikipedia.org/wiki/FASTA_format

Info fields set:

    missing_code      np.nan
    alphabet          "dna" | "rna" | "protein"
    encoders          present only when sequence IDs were encoded
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


_CHAR_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_UNKNOWN = 5

_DNA_CHARS = set("ACGTN")
_RNA_CHARS = set("ACGUN")
_PROTEIN_CHARS = set("ACDEFGHIKLMNPQRSTVWY")


class FastaReader(Reader):
    """Reader for .fasta / .fa / .fna / .faa files."""

    extensions = [".fasta", ".fa", ".fna", ".faa"]
    handles_compression = False

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"FASTA reader requires exactly two dims, got {dims}"
            )
        sequence_dim, position_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})

        ids, seqs = _parse_fasta(path)
        if not ids:
            raise ReaderError("FASTA file contains no sequences")

        max_len = max(len(s) for s in seqs)
        n = len(ids)

        data = np.full((n, max_len), np.nan, dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = _CHAR_MAP.get(ch.upper(), _UNKNOWN)

        alphabet = _infer_alphabet(seqs)

        final: dict[str, dict[str, int]] = {}
        encoders_used: dict[str, dict[str, object]] = {}

        seq_rule = labels.get(sequence_dim, "builtin")
        if seq_rule in (None, "builtin"):
            seq_labels, seq_encs = _encode_ids(
                ids, encoders_cfg, sequence_dim
            )
            final[sequence_dim] = seq_labels
            if seq_encs:
                encoders_used[sequence_dim] = seq_encs
        elif seq_rule == "auto":
            final[sequence_dim] = {str(i): i for i in range(n)}
        elif isinstance(seq_rule, dict):
            final[sequence_dim] = {
                str(k): int(v) for k, v in seq_rule.items()
            }
        else:
            raise ReaderError(
                f"FASTA reader: unsupported label rule for "
                f"'{sequence_dim}': {seq_rule!r}"
            )

        pos_rule = labels.get(position_dim, "auto")
        if pos_rule in (None, "auto"):
            final[position_dim] = {
                str(i): i for i in range(max_len)
            }
        elif isinstance(pos_rule, dict):
            final[position_dim] = {
                str(k): int(v) for k, v in pos_rule.items()
            }
        else:
            raise ReaderError(
                f"FASTA reader: unsupported label rule for "
                f"'{position_dim}': {pos_rule!r}"
            )

        info: dict = {
            "missing_code": np.nan,
            "alphabet": alphabet,
        }
        if encoders_used:
            info["encoders"] = encoders_used

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
        )


def _parse_fasta(path: Path) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    seqs: list[str] = []
    current: list[str] = []

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith(">"):
                if current:
                    seqs.append("".join(current))
                    current = []
                header = line[1:].strip()
                parts = header.split()
                sid = parts[0] if parts else f"seq{len(ids)}"
                ids.append(sid)
            else:
                current.append(line)

    if current:
        seqs.append("".join(current))

    return ids, seqs


def _infer_alphabet(seqs: list[str]) -> str:
    observed: set[str] = set()
    for seq in seqs:
        observed |= {c.upper() for c in seq}
    observed.discard("-")
    observed.discard(".")

    if observed <= _DNA_CHARS - {"T", "U"}:
        return "dna"
    if observed <= _RNA_CHARS - {"T", "U"}:
        return "rna"
    if "U" in observed and "T" not in observed:
        return "rna"
    if observed <= _DNA_CHARS:
        return "dna"
    if observed <= _PROTEIN_CHARS:
        return "protein"
    return "dna"


def _encode_ids(ids, encoders_cfg, dim_name):
    try:
        _ = np.asarray(ids, dtype=np.float32)
        return unique_labels(ids, dim_name, "fasta"), {}
    except (ValueError, TypeError):
        pass

    enc_name = encoders_cfg.get("all", "labelencoder")
    encoder = get_encoder(enc_name)
    codes = encoder.fit_transform(ids)
    labels_map = unique_labels(ids, dim_name, "fasta")
    return labels_map, {dim_name: encoder}