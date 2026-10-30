"""Mutation Annotation Format (MAF) reader.

Reads the tab-separated MAF table used by TCGA/GDC. Comment and version
lines beginning with ``#`` are skipped; the first remaining line is the
header. All columns are retained and returned as variant x field.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class MafReader(Reader):
    """Mutation Annotation Format table reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["variant", "field"], "labels": {"variant": "auto", "field": "builtin"}}
    extensions = [".maf"]
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
            raise ReaderError(f"maf reader requires exactly two dims, got {dims}")
        try:
            df = pd.read_csv(path, sep="\t", comment="#", dtype=str, low_memory=False)
        except Exception as exc:
            raise ReaderError(f"maf reader: cannot parse {path}: {exc}") from exc
        if df.shape[0] == 0 or df.shape[1] == 0:
            raise ReaderError("maf reader: table has zero rows or columns")
        df.columns = [str(c).strip() for c in df.columns]
        return table_form(
            df, dims, labels, "maf",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"variant:{i}" for i in range(df.shape[0])],
        )
