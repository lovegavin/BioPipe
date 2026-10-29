"""BEDPE reader.

Reads the 10 standard BEDPE columns. Browser and track
comment lines are ignored. Coordinates are zero-based, half-open."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BedpeReader(Reader):
    """Paired-end BED reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = ['.bedpe']
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
            raise ReaderError(f"BEDPE reader requires exactly two dims, got {dims}")
        df = df = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
        if df.shape[1] != 10:
            raise ReaderError(f"BEDPE reader: expected 10 columns, got {df.shape[1]}")
        df.columns = ["chrom1", "start1", "end1", "chrom2", "start2", "end2",
                      "name", "score", "strand1", "strand2"]
        return table_form(
            df, dims, labels, "BEDPE",
            encoders_cfg=args.get("encoders") or {},
        )
