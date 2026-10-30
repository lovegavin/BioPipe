"""UCSC chain format reader.

Each header line describes one alignment block. Only header lines are
returned; the variable-length alignment data rows are skipped. Output is
alignment x field with a fixed twelve-column schema.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

CHAIN_COLUMNS = [
    "score", "tName", "tSize", "tStrand", "tStart", "tEnd",
    "qName", "qSize", "qStrand", "qStart", "qEnd", "id",
]


class ChainReader(Reader):
    """UCSC chain alignment reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["alignment", "field"], "labels": {"alignment": "auto", "field": "builtin"}}
    extensions = [".chain"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"chain reader requires exactly two dims, got {dims}")
        rows = []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReaderError(f"chain reader: cannot read {path}: {exc}") from exc
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] != "chain":
                continue
            if len(parts) != 13:
                raise ReaderError(f"chain reader: expected 13 header fields, got {len(parts)}")
            rows.append(parts[1:])
        if not rows:
            raise ReaderError("chain reader: no chain header lines found")
        df = pd.DataFrame(rows, columns=CHAIN_COLUMNS)
        return table_form(
            df, dims, labels, "chain",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"chain:{i}" for i in range(len(df))],
        )
