"""SAM text reader.

Reads the 11 mandatory SAM fields and skips @ header lines.
Binary BAM/CRAM files are not handled by this reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class SamReader(Reader):
    """Sequence Alignment/Map text reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = ['.sam']
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
            raise ReaderError(f"SAM reader requires exactly two dims, got {dims}")
        df = rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("@"):
                continue
            parts = line.split("\t")
            if len(parts) < 11:
                raise ReaderError(f"SAM reader: expected at least 11 columns, got {len(parts)}")
            rows.append(parts[:11])
        if not rows:
            raise ReaderError("SAM reader: no alignment records")
        df = pd.DataFrame(rows, columns=[
            "qname", "flag", "rname", "pos", "mapq", "cigar", "rnext", "pnext",
            "tlen", "seq", "qual"])
        return table_form(
            df, dims, labels, "SAM",
            encoders_cfg=args.get("encoders") or {},
        )
