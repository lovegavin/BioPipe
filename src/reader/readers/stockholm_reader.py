"""Stockholm alignment reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}


class StockholmReader(Reader):
    """Reader for Stockholm alignments."""

    output_contract = reader_contract()
    file_input = {"dims": ["sequence", "position"], "labels": {"sequence": "builtin", "position": "auto"}}
    extensions = [".sto", ".stockholm", ".stk"]
    handles_compression = False
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"Stockholm reader requires exactly two dims, got {dims}")
        seq_dim, pos_dim = dims
        with open(path, encoding="utf-8") as fh:
            lines = [line.rstrip("\r\n") for line in fh]
        if not any(line.startswith("# STOCKHOLM") for line in lines):
            raise ReaderError("Stockholm reader: missing '# STOCKHOLM' header")
        order = []
        seqs: dict[str, list[str]] = {}
        for line in lines:
            if not line or line.startswith("#") or line == "//":
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            name, seq = parts[0], parts[1]
            if name not in seqs:
                seqs[name] = []
                order.append(name)
            seqs[name].append(seq)
        order = [name for name in order if "".join(seqs[name])]
        if not order:
            raise ReaderError("Stockholm reader: no sequences")
        joined = ["".join(seqs[name]) for name in order]
        width = len(joined[0])
        if any(len(seq) != width for seq in joined):
            raise ReaderError("Stockholm reader: alignment rows have different lengths")
        data = np.full((len(joined), width), np.nan, dtype=np.float32)
        for i, seq in enumerate(joined):
            for j, ch in enumerate(seq):
                data[i, j] = _CODES.get(ch.upper(), 5)
        return Form(
            data=data,
            dims=[seq_dim, pos_dim],
            labels={
                seq_dim: unique_labels(order, seq_dim, "stockholm"),
                pos_dim: {str(i): i for i in range(width)},
            },
            info={"missing_code": np.nan, "alphabet": "dna"},
        )
