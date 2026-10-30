"""Tripos MOL2 molecule reader (molecule count summary)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class Mol2Reader(Reader):
    """MOL2 reader with atom and bond counts per molecule."""

    output_contract = reader_contract()
    file_input = {"dims": ["molecule", "field"], "labels": {"molecule": "auto", "field": "builtin"}}
    extensions = [".mol2"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"MOL2 reader requires exactly two dims, got {dims}")
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
        rows = []
        i = 0
        while i < len(lines):
            if lines[i].strip() != "@<TRIPOS>MOLECULE":
                i += 1
                continue
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                break
            name = lines[i].strip()
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                raise ReaderError("MOL2 reader: molecule has no counts line")
            counts = lines[i].split()
            if len(counts) < 2:
                raise ReaderError("MOL2 reader: counts line needs atom and bond counts")
            try:
                atoms, bonds = int(counts[0]), int(counts[1])
            except ValueError as exc:
                raise ReaderError("MOL2 reader: counts must be integers") from exc
            rows.append([name, atoms, bonds])
            i += 1
        if not rows:
            raise ReaderError("MOL2 reader: no molecules")
        df = pd.DataFrame(rows, columns=["molecule", "atoms", "bonds"])
        return table_form(df, dims, labels, "MOL2", encoders_cfg=args.get("encoders") or {}, row_labels=df["molecule"].tolist())
