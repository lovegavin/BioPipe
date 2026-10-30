"""Minimal mmCIF atom_site loop reader."""
from __future__ import annotations

import shlex
from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


class MmcifReader(Reader):
    """Reader for mmCIF atom_site loops; output is atom x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["atom", "field"], "labels": {"atom": "auto", "field": "builtin"}}
    extensions = [".cif", ".mmcif"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_atoms": {"type": "integer", "minimum": 1, "default": 100000},
            "model": {"type": "integer", "minimum": 1},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        max_atoms = int(args.get("max_atoms", 100000))
        model = args.get("model")
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"mmCIF reader: cannot read {path}: {exc}") from exc
        fields = None
        rows = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line != "loop_":
                i += 1
                continue
            i += 1
            raw_fields = []
            while i < len(lines) and lines[i].strip().startswith("_"):
                raw_fields.append(lines[i].strip())
                i += 1
            if not raw_fields:
                continue
            names = [f.split(".", 1)[-1] for f in raw_fields]
            if not any(f.startswith("_atom_site.") for f in raw_fields):
                while i < len(lines) and lines[i].strip() not in ("#", "loop_"):
                    i += 1
                continue
            fields = names
            while i < len(lines):
                line = lines[i].strip()
                if not line or line.startswith("#") or line == "loop_" or line.startswith("_"):
                    break
                try:
                    tokens = shlex.split(line)
                except ValueError as exc:
                    raise ReaderError(f"mmCIF reader: malformed atom_site row: {exc}") from exc
                if len(tokens) != len(fields):
                    raise ReaderError(
                        f"mmCIF reader: expected {len(fields)} atom_site values, got {len(tokens)}"
                    )
                rows.append(tokens)
                if len(rows) >= max_atoms:
                    break
                i += 1
            break
        if fields is None or not rows:
            raise ReaderError(f"mmCIF reader: no atom_site loop in {path}")
        df = pd.DataFrame(rows, columns=fields)
        if model is not None:
            key = "pdbx_PDB_model_num"
            if key not in df.columns:
                raise ReaderError("mmCIF reader: model requested but pdbx_PDB_model_num is absent")
            df = df[pd.to_numeric(df[key], errors="coerce") == int(model)]
            if df.empty:
                raise ReaderError(f"mmCIF reader: model {model} has no atoms")
        for column in ("Cartn_x", "Cartn_y", "Cartn_z", "occupancy", "B_iso_or_equiv"):
            if column in df.columns:
                df[column] = pd.to_numeric(df[column].replace({"?": None, ".": None}), errors="coerce")
        row_labels = [
            f"{row.get('label_asym_id', '?')}:{row.get('label_seq_id', '?')}:{row.get('label_atom_id', '?')}"
            for _, row in df.iterrows()
        ]
        return table_form(
            df, dims, labels, "mmCIF", args.get("encoders", {}),
            row_labels=row_labels,
        )
