"""ENCODE narrowPeak reader."""
from __future__ import annotations

from pathlib import Path

from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import read_whitespace, table_form

_NAMES = ["chrom", "start", "end", "name", "score", "strand",
          "signalValue", "pValue", "qValue", "peak"]


class NarrowPeakReader(Reader):
    """Reader for 10-column ENCODE narrowPeak files."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".narrowpeak"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        df = read_whitespace(path, _NAMES, "narrowPeak")
        return table_form(df, dims, labels, "narrowPeak", args.get("encoders", {}))
