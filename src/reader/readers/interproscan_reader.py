"""InterProScan TSV reader (15 standard columns)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "protein_accession", "md5", "length", "analysis", "signature_accession",
    "signature_description", "start", "stop", "score", "status", "date",
    "interpro_accession", "interpro_description", "go_terms", "pathways",
]


class InterProScanReader(Reader):
    """InterProScan tabular output reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["match", "field"], "labels": {"match": "auto", "field": "builtin"}}
    extensions = [".iprscan"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"InterProScan reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 15:
                raise ReaderError(f"InterProScan reader: expected 15 columns, got {len(fields)}")
            rows.append(fields[:15])
        if not rows:
            raise ReaderError("InterProScan reader: no match rows")
        df = pd.DataFrame(rows, columns=FIELDS)
        return table_form(df, dims, labels, "InterProScan", encoders_cfg=args.get("encoders") or {})
