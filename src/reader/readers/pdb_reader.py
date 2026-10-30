"""Protein Data Bank (PDB) coordinate reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class PdbReader(Reader):
    """ATOM/HETATM coordinate reader using fixed PDB columns."""

    output_contract = reader_contract()
    file_input = {"dims": ["atom", "field"], "labels": {"atom": "auto", "field": "builtin"}}
    extensions = [".pdb", ".ent"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "integer", "minimum": 0, "default": 0},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PDB reader requires exactly two dims, got {dims}")
        wanted_model = int(args.get("model", 0))
        model = 0
        rows = []
        ids = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("MODEL"):
                try:
                    model = int(line.split()[1])
                except (IndexError, ValueError):
                    model += 1
                continue
            if line.startswith("ENDMDL"):
                model = 0
                continue
            if not (line.startswith("ATOM  ") or line.startswith("HETATM")):
                continue
            if wanted_model and model != wanted_model:
                continue
            try:
                serial = int(line[6:11])
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                occupancy = float(line[54:60] or "nan")
                bfactor = float(line[60:66] or "nan")
                residue_number = int(line[22:26])
            except (ValueError, IndexError) as exc:
                raise ReaderError(f"PDB reader: malformed coordinate line {line!r}") from exc
            rows.append({
                "x": x, "y": y, "z": z, "occupancy": occupancy,
                "bfactor": bfactor, "residue_number": float(residue_number),
                "chain": line[21:22].strip() or "_",
                "resname": line[17:20].strip() or "UNK",
                "element": line[76:78].strip() or "X",
            })
            ids.append(f"atom:{serial}")
        if not rows:
            raise ReaderError("PDB reader: no ATOM/HETATM records")
        frame = pd.DataFrame(rows)
        return table_form(
            frame, dims, labels, "PDB",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "PDB", "n_atoms": len(rows), "model": wanted_model or "all"},
        )
