"""PAF reader.

Reads the 12 mandatory PAF columns (query/target names and
coordinates, strand, alignment block length, matches and mapping
quality). Optional SAM-style tags are ignored."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class PafReader(Reader):
    """Pairwise mapping format (PAF) reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = ['.paf']
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
            raise ReaderError(f"PAF reader requires exactly two dims, got {dims}")
        df = pd.read_csv(path, sep="\t", header=None, comment="#")
        if df.shape[1] < 12:
            raise ReaderError(f"PAF reader: expected at least 12 columns, got {df.shape[1]}")
        df = df.iloc[:, :12]
        df.columns = ["query_name", "query_length", "query_start", "query_end",
                      "strand", "target_name", "target_length", "target_start",
                      "target_end", "matches", "block_length", "mapq"]
        return table_form(
            df, dims, labels, "PAF",
            encoders_cfg=args.get("encoders") or {},
        )
