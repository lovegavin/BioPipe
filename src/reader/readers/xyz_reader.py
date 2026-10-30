"""XYZ Cartesian coordinate reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_Z = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15,
    "S": 16, "Cl": 17, "Ar": 18, "K": 19, "Ca": 20, "Fe": 26, "Zn": 30,
    "Br": 35, "I": 53,
}
_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "P": 30.974, "S": 32.06, "Cl": 35.45, "Br": 79.904, "I": 126.904,
    "B": 10.81, "Si": 28.085,
}


class XyzReader(Reader):
    """XYZ reader, one row per atom."""

    output_contract = reader_contract()
    file_input = {"dims": ["atom", "feature"], "labels": {"atom": "auto", "feature": "builtin"}}
    extensions = [".xyz"]
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
            raise ReaderError(f"XYZ reader: cannot read {path}: {exc}") from exc
        if len(lines) < 2:
            raise ReaderError("XYZ reader: missing atom count or comment")
        try:
            n_atoms = int(lines[0].strip())
        except ValueError as exc:
            raise ReaderError("XYZ reader: invalid atom count") from exc
        if n_atoms <= 0 or len(lines) < 2 + n_atoms:
            raise ReaderError("XYZ reader: truncated atom block")
        rows = []
        for i, line in enumerate(lines[2:2 + n_atoms], start=1):
            parts = line.split()
            if len(parts) < 4:
                raise ReaderError(f"XYZ reader: malformed atom line {i}")
            symbol = parts[0]
            try:
                x, y, z = (float(v) for v in parts[1:4])
            except ValueError as exc:
                raise ReaderError(f"XYZ reader: invalid coordinate on atom line {i}") from exc
            rows.append([x, y, z, _Z.get(symbol, 0), _MASS.get(symbol, 0.0)])
        df = pd.DataFrame(rows, columns=["x", "y", "z", "atomic_number", "atomic_mass"])
        return table_form(
            df, dims, labels, "XYZ",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"atom{i}" for i in range(1, n_atoms + 1)],
            info_extra={"format": "XYZ", "comment": lines[1].strip(), "n_atoms": n_atoms},
        )
