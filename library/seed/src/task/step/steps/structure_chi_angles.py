"""Side-chain chi torsion angles from a full-atom structure form."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

# Atom names forming chi1 (N-CA-CB-XG), chi2 (CA-CB-XG-XD) and chi3 (CB-XG-XD-XE).
CHI1 = {
    "SER": "OG", "CYS": "SG", "THR": "OG1", "VAL": "CG1", "LEU": "CG",
    "ILE": "CG1", "MET": "SD", "PHE": "CG", "TYR": "CG", "TRP": "CG",
    "ASP": "CG", "ASN": "CG", "GLU": "CG", "GLN": "CG", "HIS": "CG",
    "LYS": "CG", "ARG": "CG", "PRO": "CG",
}
CHI2 = {
    "ASP": "OD1", "ASN": "OD1", "GLU": "CD", "GLN": "CD", "PHE": "CD1",
    "TYR": "CD1", "TRP": "CD1", "HIS": "ND1", "LYS": "CD", "ARG": "CD",
    "MET": "CE", "LEU": "CD1", "ILE": "CD1", "PRO": "CD", "VAL": "CG2",
    "THR": "CG2",
}
CHI3 = {"LYS": "CE", "ARG": "NE", "GLU": "OE1", "GLN": "OE1"}

STATISTICS = ("chi1", "chi2", "chi3")


def _fields(form: Form, field_dim: str) -> list[str]:
    labels = form.labels.get(field_dim) or {}
    return [str(name) for name in labels]


def _column(form: Form, field_dim: str, name: str) -> np.ndarray:
    fields = _fields(form, field_dim)
    if name not in fields:
        raise StepError(f"structure_chi_angles: the structure form has no '{name}' column")
    axis = 0 if list(form.dims).index(field_dim) == 0 else 1
    return form.data.take(fields.index(name), axis=axis)


def _text(form: Form, field_dim: str, name: str) -> list[str]:
    column = _column(form, field_dim, name)
    decoders = (form.info or {}).get("encoders", {}).get(field_dim, {})
    decoder = decoders.get(name)
    if decoder is not None:
        return [str(decoder.inverse_transform([float(value)])[0]) for value in column]
    return [str(int(value)) if float(value).is_integer() else f"{float(value):g}" for value in column]


def _coordinates(form: Form, field_dim: str) -> np.ndarray:
    return np.column_stack([
        _column(form, field_dim, name) for name in ("x", "y", "z")
    ]).astype(np.float64)


def dihedral(p0, p1, p2, p3) -> float:
    """Return the signed dihedral angle in degrees for four points."""
    b0 = np.asarray(p0, dtype=np.float64) - np.asarray(p1, dtype=np.float64)
    b1 = np.asarray(p2, dtype=np.float64) - np.asarray(p1, dtype=np.float64)
    b2 = np.asarray(p3, dtype=np.float64) - np.asarray(p2, dtype=np.float64)
    norm = np.linalg.norm(b1)
    if norm == 0:
        return float("nan")
    b1 = b1 / norm
    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    x = np.dot(v, w)
    y = np.dot(np.cross(b1, v), w)
    return float(np.degrees(np.arctan2(y, x)))


def residue_atoms(form: Form, atom_dim: str, field_dim: str):
    names = _text(form, field_dim, "atom_name")
    chains = _text(form, field_dim, "chain")
    numbers = _text(form, field_dim, "residue_number")
    resnames = _text(form, field_dim, "resname")
    coords = _coordinates(form, field_dim)
    groups: dict[str, dict] = {}
    order: list[str] = []
    for index, name in enumerate(names):
        label = f"{chains[index]}:{resnames[index]}:{numbers[index]}"
        if label not in groups:
            groups[label] = {"resname": resnames[index], "atoms": {}}
            order.append(label)
        groups[label]["atoms"][name.strip().upper()] = coords[index]
    return order, groups


def chi_rows(form: Form, atom_dim: str, field_dim: str) -> list[dict]:
    order, groups = residue_atoms(form, atom_dim, field_dim)
    rows = []
    for label in order:
        atoms = groups[label]["atoms"]
        resname = groups[label]["resname"].strip().upper()
        row = {name: float("nan") for name in STATISTICS}
        for name, axes in (
            ("chi1", ("N", "CA", "CB", CHI1.get(resname))),
            ("chi2", ("CA", "CB", CHI1.get(resname), CHI2.get(resname))),
            ("chi3", ("CB", CHI1.get(resname), CHI2.get(resname), CHI3.get(resname))),
        ):
            if any(axis is None for axis in axes) or any(axis not in atoms for axis in axes):
                continue
            row[name] = dihedral(*[atoms[axis] for axis in axes])
        rows.append({"residue": label, "values": row})
    return rows


class StructureChiAnglesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_chi_angles.StructureChiAnglesStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_chi_angles",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Side-chain chi angles",
        "description": "Computes chi1, chi2 and chi3 side-chain torsion angles for every residue.",
        "category": "Machine Learning",
        "icon": "Ruler",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "atom_dim", "default": "atom"},
                    {"param": "field_dim", "default": "field"},
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2,
            }],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        residue_dim = str(params.get("residue_dim") or "residue")
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_chi_angles: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )

        rows = chi_rows(form, atom_dim, field_dim)
        if not rows:
            raise StepError("structure_chi_angles: the structure form has no residues")

        data = np.asarray(
            [[row["values"][name] for name in STATISTICS] for row in rows],
            dtype=np.float32,
        )
        labels = {row["residue"]: index for index, row in enumerate(rows)}
        present = {
            name: int(np.sum(np.isfinite(data[:, column])))
            for column, name in enumerate(STATISTICS)
        }
        output = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={residue_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "n_residues": len(rows),
                "n_chi1": present["chi1"],
                "n_chi2": present["chi2"],
                "n_chi3": present["chi3"],
                "unit": "degrees",
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_residues": len(rows),
            "n_chi1": present["chi1"],
            "n_chi2": present["chi2"],
            "n_chi3": present["chi3"],
        }
        print(
            f"[structure_chi_angles] {len(rows)} residues, chi1 {present['chi1']}, "
            f"chi2 {present['chi2']}, chi3 {present['chi3']}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
