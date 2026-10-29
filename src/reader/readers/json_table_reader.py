"""JSON table reader."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


class JsonTableReader(Reader):
    """Reader for a JSON array of records or a mapping of column -> list."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "builtin"}}
    extensions = [".json"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "orient": {"type": "string", "enum": ["records", "columns"], "default": "records"},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReaderError(f"JSON table reader: cannot parse {path}: {exc}") from exc
        try:
            df = pd.DataFrame(payload)
            if args.get("orient", "records") == "columns":
                df = pd.DataFrame(payload)
        except (ValueError, TypeError) as exc:
            raise ReaderError(f"JSON table reader: unsupported JSON table shape: {exc}") from exc
        if df.ndim != 2:
            raise ReaderError("JSON table reader: JSON must describe a two-dimensional table")
        return table_form(df, dims, labels, "JSON", args.get("encoders", {}))
