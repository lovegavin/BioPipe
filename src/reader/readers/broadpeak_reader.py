"""9-column broadPeak reader."""
from __future__ import annotations

from pathlib import Path

from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import read_whitespace, table_form


class BroadPeakReader(Reader):
    """Reader for broadPeak files; output is region x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".broadpeak"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        names = [
            "chrom", "start", "end", "name", "score", "strand",
            "signal_value", "p_value", "q_value",
        ]
        df = read_whitespace(path, names, "broadPeak")
        return table_form(df, dims, labels, "broadPeak", args.get("encoders", {}))
