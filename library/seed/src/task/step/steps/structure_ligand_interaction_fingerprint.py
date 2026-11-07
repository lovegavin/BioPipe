"""Ligand-protein interaction fingerprint from a PDB atom table."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    heavy_atom_mask,
    residue_labels,
)
from src.task.step.steps._structure_common import pick_chain_sides

_CHARGED_POSITIVE = frozenset({"ARG", "LYS", "HIS"})
_CHARGED_NEGATIVE = frozenset({"ASP", "GLU"})
_AROMATIC = frozenset({"PHE", "TYR", "TRP", "HIS"})


def _required(form: Form, field_dim: str, name: str) -> int:
    index = column_index(form, field_dim, name)
    if index < 0:
        raise StepError(
            f"structure_ligand_interaction_fingerprint: the structure form has no '{name}' column"
        )
    return index


def ligand_atom_table(
    form: Form,
    atom_dim: str,
    field_dim: str,
    ligand_resnames: list[str],
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Return coordinates, element symbols and labels of the receptor atoms."""

    x = _required(form, field_dim, "x")
    y = _required(form, field_dim, "y")
    z = _required(form, field_dim, "z")
    element = _required(form, field_dim, "element")
    resname = _required(form, field_dim, "resname")
    chain = _required(form, field_dim, "chain")
    number = _required(form, field_dim, "residue_number")
    atom_name = _required(form, field_dim, "atom_name") if "atom_name" in dict(form.labels[field_dim]) else None

    data = np.asarray(form.data, dtype=np.float64)
    coords = data[:, [x, y, z]]
    elements = decode_column(form, field_dim, "element")
    names = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    numbers = data[:, number].astype(int)
    atoms = decode_column(form, field_dim, "atom_name") if atom_name is not None else None

    wanted = {str(name).upper() for name in ligand_resnames}
    receptor = np.array([str(name).upper() not in wanted for name in names], dtype=bool)
    if not receptor.any():
        raise StepError(
            "structure_ligand_interaction_fingerprint: no receptor atom is left after removing the ligand"
        )
    return coords[receptor], [str(e) for e in elements[receptor]], np.array([str(c) for c in chains[receptor]])


def fingerprint_rows(
    ligand_coords: np.ndarray,
    ligand_elements: np.ndarray,
    ligand_labels: list[str],
    protein_coords: np.ndarray,
    protein_elements: np.ndarray,
    protein_resnames: np.ndarray,
    protein_labels: list[str],
    *,
    cutoff: float = 4.0,
) -> list[dict]:
    """Count interaction types between each ligand atom and the protein."""

    if ligand_coords.size == 0:
        raise StepError("structure_ligand_interaction_fingerprint: the ligand carries no atom")
    if protein_coords.size == 0:
        raise StepError("structure_ligand_interaction_fingerprint: the protein carries no atom")
    rows = []
    for index in range(len(ligand_coords)):
        delta = protein_coords - ligand_coords[index]
        distance = np.sqrt((delta * delta).sum(axis=1))
        near = np.nonzero(distance <= cutoff)[0]
        hydrophobic = polar = charged = aromatic = 0
        for j in near:
            le = str(ligand_elements[index]).upper()
            pe = str(protein_elements[j]).upper()
            res = str(protein_resnames[j]).upper()
            if le == "C" and pe == "C":
                hydrophobic += 1
            if le in {"N", "O", "S"} and pe in {"N", "O", "S"}:
                polar += 1
            if le in {"N", "O"} and (
                (pe in {"N", "O"} and res in _CHARGED_POSITIVE | _CHARGED_NEGATIVE)
            ):
                charged += 1
            if le == "C" and res in _AROMATIC:
                aromatic += 1
        rows.append(
            {
                "label": ligand_labels[index],
                "n_contacts": int(near.size),
                "n_hydrophobic": hydrophobic,
                "n_polar": polar,
                "n_charged": charged,
                "n_aromatic": aromatic,
                "min_distance": float(distance[near].min()) if near.size else float(np.inf),
            }
        )
    return rows


class StructureLigandInteractionFingerprintStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_interaction_fingerprint.StructureLigandInteractionFingerprintStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_interaction_fingerprint",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand interaction fingerprint",
        "category": "Structure",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
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
                    "axis_info_open": False,
                },
            },
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        atom_dim = params["atom_dim"]
        field_dim = params["field_dim"]
        coords = np.asarray(form.data, dtype=np.float64)
        elements = decode_column(form, field_dim, "element")
        names = decode_column(form, field_dim, "resname")
        chains = decode_column(form, field_dim, "chain")
        numbers = np.asarray(form.data, dtype=np.float64)[:, column_index(form, field_dim, "residue_number")].astype(int)
        atoms = decode_column(form, field_dim, "atom_name")
        wanted = {str(x).upper() for x in str(params.get("ligand_resnames") or "LIG").split(",")}
        is_ligand = np.array([str(n).upper() in wanted for n in names])
        if not is_ligand.any():
            raise StepError(
                "structure_ligand_interaction_fingerprint: no ligand atom matches the requested residue names"
            )
        heavy = heavy_atom_mask(form, field_dim)
        ligand_sel = is_ligand & heavy
        protein_sel = (~is_ligand) & heavy
        if not protein_sel.any():
            raise StepError("structure_ligand_interaction_fingerprint: no protein atom is left")
        ligand_labels = [
            f"{chains[i]}:{names[i]}:{numbers[i]}:{atoms[i]}" for i in np.nonzero(ligand_sel)[0]
        ]
        rows = fingerprint_rows(
            coords[ligand_sel],
            elements[ligand_sel],
            ligand_labels,
            coords[protein_sel],
            elements[protein_sel],
            names[protein_sel],
            [f"{chains[i]}:{names[i]}:{numbers[i]}" for i in np.nonzero(protein_sel)[0]],
            cutoff=float(params.get("cutoff", 4.0)),
        )
        data = np.array(
            [[r["n_contacts"], r["n_hydrophobic"], r["n_polar"], r["n_charged"], r["n_aromatic"], r["min_distance"]] for r in rows],
            dtype=np.float32,
        )
        out_name = params.get("output", "fingerprint")
        labels = {r["label"]: i for i, r in enumerate(rows)}
        ctx[out_name] = Form(
            data=data,
            dims=["atom", "statistic"],
            labels={"atom": labels, "statistic": {"n_contacts": 0, "n_hydrophobic": 1, "n_polar": 2, "n_charged": 3, "n_aromatic": 4, "min_distance": 5}},
            info={
                "missing_code": np.nan,
                "n_ligand_atoms": len(rows),
                "n_receptor_atoms": int(protein_sel.sum()),
                "cutoff": float(params.get("cutoff", 4.0)),
            },
        )
        self._export_data = {
            "n_atoms": len(rows),
            "n_contacts": int(sum(r["n_contacts"] for r in rows)),
            "cutoff": float(params.get("cutoff", 4.0)),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
