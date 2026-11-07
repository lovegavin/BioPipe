"""Ligand-to-residue contact matrix from a PDB structure form.

Each ligand heavy atom is represented by its contacts to the surrounding
protein residues, producing a numeric matrix that downstream clustering or
heatmap operators can consume directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.forms.form import Form
from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    heavy_atom_mask,
    residue_labels,
)

_STATISTIC = ("count", "min_distance")


def _atom_labels(form, field_dim: str) -> list[str]:
    chains = decode_column(form, field_dim, "chain")
    resnames = decode_column(form, field_dim, "resname")
    numbers = decode_column(form, field_dim, "residue_number")
    names = decode_column(form, field_dim, "atom_name")
    labels: list[str] = []
    seen: dict[str, int] = {}
    for chain, resname, number, atom_name in zip(chains, resnames, numbers, names):
        base = f"{chain}:{str(resname).strip()}{int(float(number))}:{str(atom_name).strip()}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        labels.append(base if count == 0 else f"{base}#{count + 1}")
    return labels


def _mask_ligand(resnames, wanted) -> np.ndarray:
    values = {value.strip().upper() for value in wanted}
    return np.asarray([str(name).strip().upper() in values for name in resnames], dtype=bool)


def contact_matrix(ligand_coords, ligand_labels, protein_coords, protein_labels, *, cutoff, value):
    from scipy.spatial import cKDTree

    rows = ligand_labels
    columns = sorted(set(protein_labels), key=lambda label: protein_labels.index(label))
    position = {label: index for index, label in enumerate(columns)}
    counts = np.zeros((len(rows), len(columns)), dtype=np.float64)
    distances = np.full((len(rows), len(columns)), np.nan, dtype=np.float64)
    tree = cKDTree(protein_coords)
    residue_index = np.asarray([position[label] for label in protein_labels])
    for row, point in enumerate(ligand_coords):
        neighbours = tree.query_ball_point(point, r=cutoff)
        for neighbour in neighbours:
            distance = float(np.linalg.norm(point - protein_coords[neighbour]))
            column = int(residue_index[neighbour])
            counts[row, column] += 1.0
            if np.isnan(distances[row, column]) or distance < distances[row, column]:
                distances[row, column] = distance
    matrix = counts if value == "count" else distances
    return matrix, rows, columns


class StructureLigandResidueMapStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_residue_map.StructureLigandResidueMapStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_residue_map",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand residue contact map",
        "description": "Contact matrix between ligand atoms and protein residues.",
        "category": "Machine Learning",
        "icon": "GridNine",
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
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim") or "atom")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        ligand_dim = str(ctx.step_params.get("ligand_dim") or "ligand_atom")
        residue_dim = str(ctx.step_params.get("residue_dim") or "residue")
        ligand_resnames = str(ctx.step_params.get("ligand_resnames") or "LIG")
        exclude_raw = ctx.step_params.get("exclude_resnames")
        exclude_resnames = "HOH,WAT" if exclude_raw is None else str(exclude_raw)
        cutoff = float(ctx.step_params.get("cutoff", 4.0))
        value = str(ctx.step_params.get("value") or "count")
        out_name = str(ctx.step_params.get("output") or "contact_map")

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_ligand_residue_map: a PDB form with dims [{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        if not 1.0 <= cutoff <= 20.0:
            raise StepError("structure_ligand_residue_map: cutoff must be in [1, 20] angstrom")
        if value not in _STATISTIC:
            raise StepError("structure_ligand_residue_map: value must be 'count' or 'min_distance'")
        if ligand_dim == residue_dim:
            raise StepError("structure_ligand_residue_map: ligand_dim and residue_dim must differ")

        mask = heavy_atom_mask(form, field_dim)
        resnames = decode_column(form, field_dim, "resname")
        ligand = np.asarray([name.strip() for name in ligand_resnames.split(",") if name.strip()], dtype=object)
        ligand_mask = _mask_ligand(resnames, ligand) & mask
        excluded = {value.strip().upper() for value in exclude_resnames.split(",") if value.strip()}
        protein_mask = mask & ~ligand_mask & np.asarray(
            [str(name).strip().upper() not in excluded for name in resnames], dtype=bool
        )
        if not ligand_mask.any():
            raise StepError(f"structure_ligand_residue_map: no ligand atom matches ligand_resnames {ligand_resnames!r}")
        if not protein_mask.any():
            raise StepError("structure_ligand_residue_map: the structure has no protein heavy atoms")

        coords = np.asarray(
            form.data[:, [column_index(form, field_dim, name) for name in ("x", "y", "z")]],
            dtype=np.float64,
        )
        labels = _atom_labels(form, field_dim)
        ligand_coords = coords[ligand_mask]
        ligand_labels = np.asarray(labels, dtype=object)[ligand_mask]
        protein_coords = coords[protein_mask]
        protein_labels = [
            f"{chain}:{str(resname).strip()}{int(float(number))}"
            for chain, resname, number, keep in zip(
                decode_column(form, field_dim, "chain"),
                decode_column(form, field_dim, "resname"),
                decode_column(form, field_dim, "residue_number"),
                protein_mask,
            )
            if keep
        ]

        matrix, row_labels, column_labels = contact_matrix(
            ligand_coords,
            ligand_labels,
            protein_coords,
            protein_labels,
            cutoff=cutoff,
            value=value,
        )
        data = np.asarray(matrix, dtype=np.float32)
        out = Form(
            data=data,
            dims=[ligand_dim, residue_dim],
            labels={
                ligand_dim: {label: position for position, label in enumerate(row_labels)},
                residue_dim: {label: position for position, label in enumerate(column_labels)},
            },
            info={
                "cutoff": cutoff,
                "value": value,
                "ligand_resnames": list(ligand),
                "n_ligand_atoms": int(len(row_labels)),
                "n_residues": int(len(column_labels)),
                "n_contacts": int(np.sum(~np.isnan(matrix))) if value == "min_distance" else int(np.sum(matrix > 0)),
                "unit": "A",
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_ligand_atoms": int(len(row_labels)),
            "n_residues": int(len(column_labels)),
            "n_contacts": int(out.info["n_contacts"]),
            "cutoff": cutoff,
            "value": value,
        }
        print(
            f"[structure_ligand_residue_map] {self._export_data['n_ligand_atoms']} ligand atoms x "
            f"{self._export_data['n_residues']} residues, {self._export_data['n_contacts']} contacts"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
