"""Cytogenetic band reader.

Reads the five-column UCSC cytoband table:
chrom, start, end, band name and stain."""
from __future__ import annotations

from pathlib import Path


from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import read_whitespace, table_form


class CytobandReader(Reader):
    """Cytogenetic band reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = ['.cytoband']
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
            raise ReaderError(f"cytoband reader requires exactly two dims, got {dims}")
        df = df = read_whitespace(path, ["chrom", "start", "end", "name", "stain"], "cytoband")
        return table_form(
            df, dims, labels, "cytoband",
            encoders_cfg=args.get("encoders") or {},
        )
