"""GROMACS GRO coordinate reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class GroReader(Reader):
    """GROMACS GRO reader, one row per atom."""

    output_contract = reader_contract()
    file_input = {"dims": ["atom", "feature"], "labels": {"atom": "auto", "feature": "builtin"}}
    extensions = [".gro"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"GRO reader: cannot read {path}: {exc}") from exc
        if len(lines) < 3:
            raise ReaderError("GRO reader: file is too short")
        try:
            n_atoms = int(lines[1].strip())
        except ValueError as exc:
            raise ReaderError("GRO reader: invalid atom count") from exc
        if n_atoms <= 0 or len(lines) < 2 + n_atoms:
            raise ReaderError("GRO reader: truncated atom block")
        rows = []
        for i, line in enumerate(lines[2:2 + n_atoms], start=1):
            if len(line) < 44:
                raise ReaderError(f"GRO reader: atom line {i} is too short")
            try:
                residue_number = int(line[0:5]); atom_number = int(line[15:20])
                x, y, z = float(line[20:28]), float(line[28:36]), float(line[36:44])
            except ValueError as exc:
                raise ReaderError(f"GRO reader: malformed numeric fields on atom line {i}") from exc
            rows.append([x, y, z, residue_number, atom_number,
                         line[5:10].strip(), line[10:15].strip()])
        df = pd.DataFrame(rows, columns=["x", "y", "z", "residue_number", "atom_number",
                                         "residue_name", "atom_name"])
        return table_form(
            df, dims, labels, "GRO",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"atom{i}" for i in range(1, n_atoms + 1)],
            info_extra={"format": "GRO", "n_atoms": n_atoms, "box": lines[2 + n_atoms].strip()},
        )
