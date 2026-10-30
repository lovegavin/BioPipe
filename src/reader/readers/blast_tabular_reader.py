"""BLAST tabular (outfmt 6) reader.

Reads the 12 standard BLAST columns. Additional outfmt 6 columns are
ignored; use a dedicated reader for custom column sets."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BlastTabularReader(Reader):
    """BLAST outfmt 6 reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["hit", "field"], "labels": {"hit": "auto", "field": "builtin"}}
    extensions = [".blast6", ".b6", ".blasttab"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"BLAST tabular reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 12:
                raise ReaderError(f"BLAST tabular reader: expected at least 12 columns, got {len(fields)}")
            rows.append(fields[:12])
        if not rows:
            raise ReaderError("BLAST tabular reader: no alignment rows")
        df = pd.DataFrame(rows, columns=[
            "query_id", "subject_id", "identity", "alignment_length", "mismatches",
            "gap_opens", "query_start", "query_end", "subject_start", "subject_end",
            "evalue", "bitscore",
        ])
        return table_form(df, dims, labels, "BLAST tabular", encoders_cfg=args.get("encoders") or {})
