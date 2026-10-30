"""SDF molecular record summary reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form

_MASS = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "S": 32.06,
    "P": 30.974, "F": 18.998, "Cl": 35.45, "Br": 79.904, "I": 126.904,
    "B": 10.81, "Si": 28.085, "Se": 78.971, "Na": 22.990, "K": 39.098,
}


class SdfReader(Reader):
    """Reader for SDF records; output is molecule x [atoms, bonds, molecular_weight]."""

    output_contract = reader_contract()
    file_input = {"dims": ["molecule", "field"], "labels": {"molecule": "auto", "field": "builtin"}}
    extensions = [".sdf"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_records": {"type": "integer", "minimum": 1, "default": 10000},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        max_records = int(args.get("max_records", 10000))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ReaderError(f"SDF reader: cannot read {path}: {exc}") from exc
        records = text.split("$$$$")
        rows = []
        molecule_ids = []
        for index, record in enumerate(records):
            if len(rows) >= max_records:
                break
            if not record.strip():
                continue
            lines = record.splitlines()
            if len(lines) < 4:
                raise ReaderError(f"SDF reader: record {index + 1} has fewer than 4 header lines")
            counts = lines[3]
            try:
                n_atoms = int(counts[0:3])
                n_bonds = int(counts[3:6])
            except (ValueError, IndexError) as exc:
                raise ReaderError(f"SDF reader: invalid counts line in record {index + 1}") from exc
            if len(lines) < 4 + n_atoms:
                raise ReaderError(f"SDF reader: truncated atom block in record {index + 1}")
            weight = 0.0
            for atom in lines[4:4 + n_atoms]:
                symbol = atom[31:34].strip() if len(atom) >= 34 else ""
                if symbol and symbol[0].isupper():
                    symbol = symbol[0] + symbol[1:].lower() if len(symbol) > 1 else symbol
                weight += _MASS.get(symbol, 0.0)
            rows.append([float(n_atoms), float(n_bonds), float(weight)])
            molecule_ids.append(f"mol:{index + 1}")
        if not rows:
            raise ReaderError(f"SDF reader: no records in {path}")
        df = pd.DataFrame(rows, columns=["atoms", "bonds", "molecular_weight"])
        return table_form(
            df, dims, labels, "SDF", args.get("encoders", {}),
            row_labels=molecule_ids,
        )
