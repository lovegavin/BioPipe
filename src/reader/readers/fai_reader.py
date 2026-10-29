"""SAM/FASTA .fai index reader."""
from __future__ import annotations

from pathlib import Path

from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import read_whitespace, table_form


class FaiReader(Reader):
    """Reader for 5-column .fai sequence index files."""

    output_contract = reader_contract()
    file_input = {"dims": ["record", "field"], "labels": {"record": "auto", "field": "builtin"}}
    extensions = [".fai"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        df = read_whitespace(path, ["name", "length", "offset", "linebases", "linewidth"], "FAI")
        return table_form(df, dims, labels, "FAI", args.get("encoders", {}))
