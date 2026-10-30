"""ENCODE bedMethyl reader (standard 15 columns)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "chrom", "start", "end", "name", "score", "strand", "thick_start",
    "thick_end", "item_rgb", "coverage", "freq_c", "freq_t", "freq_g",
    "freq_a", "freq_n",
]


class BedMethylReader(Reader):
    """bedMethyl reader (15-column ENCODE layout)."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".bedmethyl"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"bedMethyl reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 15:
                raise ReaderError(f"bedMethyl reader: expected 15 columns, got {len(fields)}")
            rows.append(fields[:15])
        if not rows:
            raise ReaderError("bedMethyl reader: no regions")
        df = pd.DataFrame(rows, columns=FIELDS)
        return table_form(df, dims, labels, "bedMethyl", encoders_cfg=args.get("encoders") or {})
