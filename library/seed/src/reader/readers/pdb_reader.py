"""Protein Data Bank (PDB) coordinate reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

_FIELDS = (
    "x", "y", "z", "occupancy", "bfactor", "residue_number",
    "chain", "resname", "element", "atom_name", "altloc", "insertion_code",
)


class PdbReader(Reader):
    provider = 'operon-readers'
    """ATOM/HETATM coordinate reader using fixed PDB columns."""
    parameters_file = 'pdb_reader.PdbReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PdbReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'ATOM/HETATM coordinate reader using fixed PDB columns',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'ATOM/HETATM coordinate reader using fixed PDB columns.',
     'extensions': ['.pdb', '.ent'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['atom', 'field'], 'labels': {'atom': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PDB reader requires exactly two dims, got {dims}")
        wanted_model = int(args.get("model", 0))
        records = str(args.get("records", "all")).strip().lower()
        if records not in ("atom", "hetatm", "all"):
            raise ReaderError("PDB reader: records must be atom, hetatm or all")
        exclude_solvent = bool(args.get("exclude_solvent", False))
        solvent = {"HOH", "WAT", "DOD", "H2O"}
        skipped = 0
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
            is_atom = line.startswith("ATOM  ")
            is_hetero = line.startswith("HETATM")
            if not (is_atom or is_hetero):
                continue
            if (records == "atom" and not is_atom) or (records == "hetatm" and not is_hetero):
                continue
            if exclude_solvent and line[17:20].strip() in solvent:
                skipped += 1
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
                "atom_name": line[12:16].strip() or "X",
                "altloc": line[16:17].strip() or "_",
                "insertion_code": line[26:27].strip() or "_",
            })
            ids.append(f"atom:{serial}")
        if not rows:
            raise ReaderError("PDB reader: no ATOM/HETATM records")
        frame = pd.DataFrame(rows)
        return table_form(
            frame, dims, labels, "PDB",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={
                "format": "PDB",
                "n_atoms": len(rows),
                "records": records,
                "exclude_solvent": exclude_solvent,
                "n_excluded_solvent": skipped,
                "model": wanted_model or "all",
                "fields": list(_FIELDS),
            },
        )
