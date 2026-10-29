"""FASTQ read reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


class FastqReader(Reader):
    """Reader for 4-line FASTQ records, exposed as read x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["read", "field"], "labels": {"read": "auto", "field": "builtin"}}
    extensions = [".fastq", ".fq"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"FASTQ reader requires exactly two dims, got {dims}")
        read_dim, field_dim = dims
        records = _parse_fastq(path)
        if not records:
            raise ReaderError("FASTQ file contains no records")
        rows = []
        for rid, seq, qual in records:
            rows.append([rid, seq, qual, len(seq)])
        cols = ["id", "sequence", "quality", "length"]
        data = np.empty((len(rows), 4), dtype=np.float64)
        encoders = {}
        for j, col in enumerate(cols):
            values = [r[j] for r in rows]
            if col == "length":
                data[:, j] = [float(v) for v in values]
                continue
            enc = get_encoder((args.get("encoders") or {}).get(col, "labelencoder"))
            data[:, j] = enc.fit_transform([str(v) for v in values])
            encoders[col] = enc
        final = {
            read_dim: unique_labels([r[0] for r in rows], read_dim, "fastq"),
            field_dim: unique_labels(cols, field_dim, "fastq"),
        }
        return Form(
            data=compact_numeric(data),
            dims=[read_dim, field_dim],
            labels=final,
            info={"missing_code": np.nan, "encoders": {field_dim: encoders}},
        )


def _parse_fastq(path: Path):
    with open(path, encoding="utf-8") as fh:
        lines = [line.rstrip("\r\n") for line in fh]
    lines = [line for line in lines if line != ""]
    if len(lines) % 4:
        raise ReaderError("FASTQ reader: record count is not a multiple of four")
    records = []
    for i in range(0, len(lines), 4):
        header, seq, plus, qual = lines[i:i + 4]
        if not header.startswith("@"):
            raise ReaderError(f"FASTQ reader: record {i // 4} header must start with '@'")
        if not plus.startswith("+"):
            raise ReaderError(f"FASTQ reader: record {i // 4} separator must start with '+'")
        if len(seq) != len(qual):
            raise ReaderError(f"FASTQ reader: record {i // 4} sequence/quality length mismatch")
        records.append((header[1:].split()[0] or f"read{i // 4}", seq, qual))
    return records
