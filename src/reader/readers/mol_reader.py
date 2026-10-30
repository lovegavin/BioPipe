"""MDL MOL/SDF V2000 molecule summary reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_ATOMIC_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "P": 30.974, "S": 32.06, "Cl": 35.45, "Br": 79.904, "I": 126.904,
    "B": 10.81, "Si": 28.085, "Se": 78.971, "Na": 22.990, "K": 39.098,
    "Mg": 24.305, "Ca": 40.078, "Fe": 55.845, "Zn": 65.38,
}


class MolReader(Reader):
    """Read one MDL MOL V2000 file and summarize its atom/bond block."""

    output_contract = reader_contract()
    file_input = {"dims": ["molecule", "feature"], "labels": {"molecule": "auto", "feature": "builtin"}}
    extensions = [".mol"]
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
            raise ReaderError(f"MOL reader: cannot read {path}: {exc}") from exc
        if len(lines) < 4:
            raise ReaderError("MOL reader: file is too short")
        counts = lines[3]
        try:
            n_atoms = int(counts[0:3]); n_bonds = int(counts[3:6])
        except (ValueError, IndexError) as exc:
            raise ReaderError("MOL reader: invalid V2000 counts line") from exc
        if n_atoms < 0 or n_bonds < 0 or len(lines) < 4 + n_atoms:
            raise ReaderError("MOL reader: truncated atom block")
        heavy = 0; mass = 0.0
        for line in lines[4:4 + n_atoms]:
            symbol = line[31:34].strip() if len(line) >= 34 else ""
            if not symbol:
                parts = line.split()
                symbol = parts[3] if len(parts) > 3 else ""
            if symbol and symbol != "H":
                heavy += 1
            mass += _ATOMIC_MASS.get(symbol, 0.0)
        df = __import__("pandas").DataFrame({
            "atoms": [n_atoms], "bonds": [n_bonds], "heavy_atoms": [heavy], "molecular_weight": [mass],
        })
        return table_form(
            df, dims, labels, "MOL",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[path.stem],
            info_extra={"format": "MOL", "n_atoms": n_atoms, "n_bonds": n_bonds},
        )
