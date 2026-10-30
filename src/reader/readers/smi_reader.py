"""SMILES line reader.

The heavy-atom count is a simple token approximation, not a full
chemical formula parser; it is documented rather than hidden."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

TOKEN = re.compile(r"\[[^\]]+\]|[A-Z][a-z]?|[a-z]")


class SmiReader(Reader):
    """SMILES .smi reader with length and approximate heavy-atom count."""

    output_contract = reader_contract()
    file_input = {"dims": ["molecule", "field"], "labels": {"molecule": "auto", "field": "builtin"}}
    extensions = [".smi"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"SMILES reader requires exactly two dims, got {dims}")
        rows = []
        for i, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()):
            if not line.strip():
                continue
            fields = line.split()
            smiles = fields[0]
            name = fields[1] if len(fields) > 1 else f"molecule:{i}"
            heavy = sum(1 for t in TOKEN.findall(smiles) if not (len(t) == 1 and t.lower() == "h"))
            rows.append([name, smiles, len(smiles), heavy])
        if not rows:
            raise ReaderError("SMILES reader: no molecules")
        df = pd.DataFrame(rows, columns=["molecule", "smiles", "length", "heavy_atoms"])
        return table_form(df, dims, labels, "SMILES", encoders_cfg=args.get("encoders") or {}, row_labels=df["molecule"].tolist())
