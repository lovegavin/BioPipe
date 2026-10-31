"""Shared encoding for text alignment readers."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.reader.readers._table_common import labels_for

_CHAR_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_UNKNOWN = 5


def alignment_form(ids, seqs, dims, labels, format_name: str):
    if len(dims) != 2:
        from src.core import ReaderError
        raise ReaderError(f"{format_name} reader requires exactly two dims, got {dims}")
    if not ids:
        from src.core import ReaderError
        raise ReaderError(f"{format_name} reader contains no sequences")
    sequence_dim, position_dim = dims
    lengths = {len(s) for s in seqs}
    if len(lengths) != 1:
        from src.core import ReaderError
        raise ReaderError(f"{format_name} reader requires aligned sequences of equal length")
    width = lengths.pop()
    data = np.full((len(ids), width), np.nan, dtype=np.float32)
    for i, seq in enumerate(seqs):
        for j, ch in enumerate(seq):
            if ch in "-.":
                continue
            data[i, j] = _CHAR_MAP.get(ch.upper(), _UNKNOWN)
    final = {
        sequence_dim: labels_for(ids, sequence_dim, labels.get(sequence_dim), format_name),
        position_dim: labels_for(list(range(width)), position_dim, labels.get(position_dim), format_name),
    }
    info = {
        "missing_code": np.nan,
        "alphabet": "dna",
        "representation": "sequence_codes",
        "alphabet_map": dict(_CHAR_MAP),
        "unknown_code": _UNKNOWN,
    }
    return Form(data=data, dims=list(dims), labels=final, info=info)


def read_clustal(path, format_name="clustal"):
    order = []
    seqs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.upper().startswith(("CLUSTAL", "MUSCLE")):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        seq = "".join(parts[1:])
        if name not in seqs:
            order.append(name)
            seqs[name] = ""
        seqs[name] += seq
    return order, [seqs[name] for name in order]


def read_nexus(path, format_name="nexus"):
    order = []
    seqs = {}
    in_matrix = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not in_matrix:
            if stripped.upper().startswith("MATRIX"):
                in_matrix = True
            continue
        if not stripped:
            continue
        if stripped.startswith(";"):
            break
        parts = stripped.split()
        if len(parts) < 2:
            continue
        name = parts[0].strip("'\"")
        seq = "".join(parts[1:]).rstrip(";")
        if name not in seqs:
            order.append(name)
            seqs[name] = ""
        seqs[name] += seq
    return order, [seqs[name] for name in order]
