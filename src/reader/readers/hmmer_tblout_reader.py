"""HMMER3 tblout reader.

Reads the 18 fixed tblout fields and the free-text target description.
Comment lines beginning with '#' are skipped."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "target_name", "target_accession", "query_name", "query_accession",
    "full_evalue", "full_score", "full_bias", "best_evalue", "best_score",
    "best_bias", "exp", "reg", "clu", "ov", "env", "dom", "rep", "inc",
]


class HmmerTbloutReader(Reader):
    """HMMER3 --tblout reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["hit", "field"], "labels": {"hit": "auto", "field": "builtin"}}
    extensions = [".tblout"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"HMMER tblout reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split(maxsplit=18)
            if len(fields) < 18:
                raise ReaderError(f"HMMER tblout reader: expected at least 18 fields, got {len(fields)}")
            desc = fields[18] if len(fields) > 18 else ""
            rows.append(fields[:18] + [desc])
        if not rows:
            raise ReaderError("HMMER tblout reader: no hit rows")
        df = pd.DataFrame(rows, columns=FIELDS + ["description"])
        return table_form(df, dims, labels, "HMMER tblout", encoders_cfg=args.get("encoders") or {})
