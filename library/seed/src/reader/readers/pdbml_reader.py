"""PDBML (PDB XML) coordinate reader.

PDBML packs the same coordinate table as PDB into an XML document. This
reader walks the ``atom_siteCategory`` entries with the standard library
parser and mirrors :class:`PdbReader`: one row per atom and the field
columns ``x``, ``y``, ``z``, ``occupancy``, ``bfactor``,
``residue_number``, ``chain``, ``resname`` and ``element``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

_FIELDS = ("x", "y", "z", "occupancy", "bfactor", "residue_number", "chain", "resname", "element")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element) -> str:
    return (element.text or "").strip() if element is not None else ""


def _number(value: str, default: float = float("nan")) -> float:
    if value in ("", ".", "?"):
        return default
    try:
        return float(value)
    except ValueError:
        return default


class PdbmlReader(Reader):
    """Read the coordinate table of a PDBML document."""

    provider = 'operon-readers'
    parameters_file = 'pdbml_reader.PdbmlReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PdbmlReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'PDBML coordinate reader',
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
     'description': 'PDBML coordinate reader with the same fields as the PDB reader.',
     'extensions': ['.pdbml'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['atom', 'field'], 'labels': {'atom': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PDBML reader requires exactly two dims, got {dims}")
        wanted_model = int(args.get("model", 0))
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise ReaderError(f"PDBML reader: invalid XML: {exc}") from exc

        rows = []
        ids = []
        for site in root.iter():
            if _local(site.tag) != "atom_site":
                continue
            values = {}
            for child in site:
                values[_local(child.tag)] = _text(child)
            group = values.get("group_PDB", "ATOM") or "ATOM"
            if group not in ("ATOM", "HETATM"):
                continue
            model_text = values.get("pdbx_PDB_model_num", "1")
            try:
                model = int(model_text)
            except ValueError:
                model = 1
            if wanted_model and model != wanted_model:
                continue
            x = _number(values.get("Cartn_x", ""))
            y = _number(values.get("Cartn_y", ""))
            z = _number(values.get("Cartn_z", ""))
            if not np.isfinite([x, y, z]).all():
                raise ReaderError(
                    "PDBML reader: atom_site record is missing Cartesian coordinates"
                )
            residue_text = values.get("label_seq_id") or values.get("auth_seq_id") or ""
            chain = values.get("label_asym_id") or values.get("auth_asym_id") or "_"
            resname = values.get("label_comp_id") or values.get("auth_comp_id") or "UNK"
            element = values.get("type_symbol") or "X"
            atom_id = values.get("label_atom_id") or values.get("auth_atom_id") or "?"
            rows.append({
                "x": x,
                "y": y,
                "z": z,
                "occupancy": _number(values.get("occupancy", "")),
                "bfactor": _number(values.get("B_iso_or_equiv", "")),
                "residue_number": _number(residue_text),
                "chain": chain or "_",
                "resname": resname or "UNK",
                "element": element or "X",
            })
            serial = site.get("id") or f"{chain}:{residue_text}:{atom_id}"
            ids.append(f"atom:{serial}")

        if not rows:
            raise ReaderError("PDBML reader: no ATOM/HETATM records")
        frame = pd.DataFrame(rows, columns=list(_FIELDS))
        return table_form(
            frame, dims, labels, "PDBML",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={
                "format": "PDBML",
                "n_atoms": len(rows),
                "model": wanted_model or "all",
            },
        )
