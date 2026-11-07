"""Backbone phi/psi dihedrals and Ramachandran region classes."""

from __future__ import annotations

import numpy as np
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column
from src.task.step.steps._structure_common import (
    field_columns,
    heavy_atom_mask,
    residue_labels,
)

REGIONS = ("alpha", "beta", "left_alpha", "other")
_REGION_INDEX = {name: index for index, name in enumerate(REGIONS)}


def dihedral(p0, p1, p2, p3) -> float:
    """Return the signed dihedral angle in degrees (NaN when degenerate)."""
    b0 = np.asarray(p1, float) - np.asarray(p0, float)
    b1 = np.asarray(p2, float) - np.asarray(p1, float)
    b2 = np.asarray(p3, float) - np.asarray(p2, float)
    n1 = np.cross(b0, b1)
    n2 = np.cross(b1, b2)
    denominator = np.linalg.norm(n1) * np.linalg.norm(n2)
    if denominator < 1e-9:
        return float("nan")
    x = float(np.dot(n1, n2) / denominator)
    y = float(np.dot(np.cross(n1, n2), b1) / (denominator * np.linalg.norm(b1)))
    return float(np.degrees(np.arctan2(y, np.clip(x, -1.0, 1.0))))


def ramachandran_region(phi: float, psi: float) -> str:
    """Classify one (phi, psi) pair into a coarse Ramachandran region."""
    if not np.isfinite(phi) or not np.isfinite(psi):
        return "other"
    if -100.0 <= phi <= -30.0 and -70.0 <= psi <= 10.0:
        return "alpha"
    if -170.0 <= phi <= -60.0 and (psi >= 100.0 or psi <= -150.0):
        return "beta"
    if 30.0 <= phi <= 100.0 and 0.0 <= psi <= 80.0:
        return "left_alpha"
    return "other"


def residue_backbone(form: Form, atom_dim: str, field_dim: str) -> list[dict]:
    """Group N, CA and C coordinates per residue in structure order."""
    fields = ("atom_name", "chain", "residue_number", "x", "y", "z")
    field_columns(form, field_dim, fields)
    atom_names = decode_column(form, field_dim, "atom_name")
    chains = decode_column(form, field_dim, "chain")
    numbers = decode_column(form, field_dim, "residue_number")
    coords = np.column_stack(
        [
            np.asarray(form.data[:, form.labels[field_dim][axis]], dtype=float)
            for axis in ("x", "y", "z")
        ]
    )
    mask = heavy_atom_mask(form, field_dim)
    labels = residue_labels(form, field_dim)
    entries: dict[str, dict] = {}
    order: list[str] = []
    for index in range(len(atom_names)):
        if not mask[index]:
            continue
        label = labels[index]
        entry = entries.get(label)
        if entry is None:
            entry = {"label": label, "chain": chains[index], "number": numbers[index]}
            entries[label] = entry
            order.append(label)
        name = str(atom_names[index]).strip().upper()
        if name in ("N", "CA", "C"):
            entry[name] = coords[index]
    return [entries[label] for label in order]


def phi_psi_rows(residues: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for index, entry in enumerate(residues):
        phi = float("nan")
        psi = float("nan")
        if index > 0 and residues[index - 1]["chain"] == entry["chain"]:
            previous = residues[index - 1]
            if all(key in previous for key in ("C",)) and all(
                key in entry for key in ("N", "CA", "C")
            ):
                phi = dihedral(previous["C"], entry["N"], entry["CA"], entry["C"])
        if index + 1 < len(residues) and residues[index + 1]["chain"] == entry["chain"]:
            following = residues[index + 1]
            if all(key in entry for key in ("N", "CA", "C")) and "N" in following:
                psi = dihedral(entry["N"], entry["CA"], entry["C"], following["N"])
        rows.append(
            {
                "label": entry["label"],
                "phi": phi,
                "psi": psi,
                "region": _REGION_INDEX[ramachandran_region(phi, psi)],
            }
        )
    return rows


def _finite_range(values: np.ndarray) -> list[float] | None:
    """Return [min, max] over finite entries, or None when all are NaN."""
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return None
    return [float(finite.min()), float(finite.max())]


class StructurePhiPsiStep(Step):
    """Per-residue backbone dihedrals and coarse Ramachandran classes."""

    provider = "operon-core"
    parameters_file = "structure_phi_psi.StructurePhiPsiStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_phi_psi",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Backbone phi/psi and Ramachandran regions",
        "description": (
            "Computes per-residue phi and psi dihedrals from a full-atom PDB form "
            "and labels each residue with a coarse Ramachandran region."
        ),
        "category": "Machine Learning",
        "icon": "Ruler",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
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
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        residue_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "dihedrals"))

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_phi_psi: a PDB form with dims [{atom_dim}, {field_dim}] is "
                f"required, got {list(form.dims)}"
            )
        residues = residue_backbone(form, atom_dim, field_dim)
        if len(residues) < 2:
            raise StepError(
                "structure_phi_psi: at least two residues with backbone atoms are required"
            )
        rows = phi_psi_rows(residues)
        labels = [row["label"] for row in rows]
        data = np.asarray(
            [[row["phi"], row["psi"], row["region"]] for row in rows], dtype=np.float32
        )
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {"phi": 0, "psi": 1, "region": 2},
            },
            info={
                "missing_code": np.nan,
                "regions": list(REGIONS),
                "region_codes": {name: index for index, name in enumerate(REGIONS)},
                "n_residues": len(rows),
            },
        )
        out.validate()
        counts = {name: 0 for name in REGIONS}
        for row in rows:
            counts[REGIONS[int(row["region"])]] += 1
        self._export_data = {
            "n_residues": len(rows),
            "regions": counts,
            "phi_range": _finite_range(data[:, 0]),
            "psi_range": _finite_range(data[:, 1]),
        }
        ctx[out_name] = out
        print(
            f"[structure_phi_psi] {len(rows)} residues, regions {counts}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
