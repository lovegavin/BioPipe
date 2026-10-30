"""Generic 9-column GFF reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


class GffReader(Reader):
    """Reader for 9-column GFF files; output is feature x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["feature", "field"], "labels": {"feature": "auto", "field": "builtin"}}
    extensions = [".gff2"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        names = [
            "seqid", "source", "type", "start", "end", "score",
            "strand", "phase", "attributes",
        ]
        try:
            df = pd.read_csv(path, sep="\t", header=None, comment="#", dtype=str)
        except Exception as exc:
            raise ReaderError(f"GFF reader: cannot parse {path}: {exc}") from exc
        if df.shape[1] != len(names):
            raise ReaderError(f"GFF reader: expected 9 columns, got {df.shape[1]}")
        df.columns = names
        for column in ("start", "end", "score", "phase"):
            df[column] = pd.to_numeric(df[column].replace(".", pd.NA), errors="coerce")
        df = df.dropna(subset=["start", "end"])
        if df.empty:
            raise ReaderError(f"GFF reader: no usable features in {path}")
        row_labels = [
            f"{row.seqid}:{int(row.start)}-{int(row.end)}:{row.type}"
            for row in df.itertuples(index=False)
        ]
        return table_form(
            df, dims, labels, "GFF", args.get("encoders", {}),
            row_labels=row_labels,
        )
