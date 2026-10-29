"""bedGraph signal track reader."""
from __future__ import annotations

from pathlib import Path

from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import read_whitespace, table_form


class BedGraphReader(Reader):
    """Reader for 4-column bedGraph files; output is region x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".bedgraph", ".bdg"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        df = read_whitespace(path, ["chrom", "start", "end", "value"], "bedGraph")
        return table_form(df, dims, labels, "bedGraph", args.get("encoders", {}))
