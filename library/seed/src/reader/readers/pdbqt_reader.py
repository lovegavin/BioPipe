"""AutoDock PDBQT coordinate reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

_FIELDS = (
    "x", "y", "z", "occupancy", "bfactor", "residue_number",
    "chain", "resname", "element", "atom_name", "altloc", "insertion_code",
    "partial_charge", "atom_type",
)


def _element(atom_name: str, atom_type: str) -> str:
    """Derive the chemical element from the AutoDock atom type."""
    kind = (atom_type or "").strip().upper()
    if len(kind) >= 2 and kind[:2] in ("CL", "BR"):
        return kind[:2]
    if kind:
        return kind[0]
    letter = (atom_name or "").strip()[:1].upper()
    return letter or "X"


def _charge_and_type(line: str) -> tuple[float, str]:
    """Read the partial charge and AutoDock atom type from a PDBQT line."""
    try:
        charge = float(line[70:76])
        atom_type = line[77:79].strip()
        if atom_type:
            return charge, atom_type
    except (ValueError, IndexError):
        pass
    tokens = line.split()
    if len(tokens) >= 13:
        try:
            return float(tokens[-2]), tokens[-1]
        except ValueError:
            pass
    raise ReaderError(f"PDBQT reader: malformed charge/atom-type columns {line!r}")


class PdbqtReader(Reader):
    provider = 'operon-readers'
    """AutoDock PDBQT coordinate reader with partial charges and atom types."""
    parameters_file = 'pdbqt_reader.PdbqtReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PdbqtReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'AutoDock PDBQT coordinate reader',
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
     'description': 'ATOM/HETATM records with AutoDock partial charges and atom types.',
     'extensions': ['.pdbqt'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['atom', 'field'], 'labels': {'atom': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PDBQT reader requires exactly two dims, got {dims}")
        rows = []
        ids = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not (line.startswith("ATOM  ") or line.startswith("HETATM")):
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
                raise ReaderError(
                    f"PDBQT reader: malformed coordinate line {line!r}"
                ) from exc
            partial_charge, atom_type = _charge_and_type(line)
            atom_name = line[12:16].strip() or "X"
            rows.append({
                "x": x, "y": y, "z": z, "occupancy": occupancy,
                "bfactor": bfactor, "residue_number": float(residue_number),
                "chain": line[21:22].strip() or "_",
                "resname": line[17:20].strip() or "UNK",
                "element": _element(atom_name, line[76:79]),
                "atom_name": atom_name,
                "altloc": line[16:17].strip() or "_",
                "insertion_code": line[26:27].strip() or "_",
                "partial_charge": partial_charge,
                "atom_type": atom_type,
            })
            ids.append(f"atom:{serial}")
        if not rows:
            raise ReaderError("PDBQT reader: no ATOM/HETATM records")
        frame = pd.DataFrame(rows)
        return table_form(
            frame, dims, labels, "PDBQT",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={
                "format": "PDBQT",
                "n_atoms": len(rows),
                "fields": list(_FIELDS),
                "has_partial_charge": True,
                "has_autodock_type": True,
            },
        )
