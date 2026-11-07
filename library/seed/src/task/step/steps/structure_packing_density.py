"""Residue packing density from neighbour atom counts."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
)
from src.task.step.steps._structure_common import atom_coords, field_columns
from src.task.step.steps._protein_common import residue_order


def residue_centers(
    coords: np.ndarray,
    labels: list[str],
    names: np.ndarray | None,
) -> dict[str, np.ndarray]:
    """One centre per residue: the CA coordinate when available, else the atom mean."""

    per_residue: dict[str, list[int]] = {}
    for index, label in enumerate(labels):
        per_residue.setdefault(label, []).append(index)
    centers: dict[str, np.ndarray] = {}
    for label, indices in per_residue.items():
        chosen = None
        if names is not None:
            for index in indices:
                if str(names[index]).strip().upper() == "CA":
                    chosen = index
                    break
        centers[label] = coords[chosen] if chosen is not None else coords[indices].mean(axis=0)
    return centers


def packing_rows(
    coords: np.ndarray,
    labels: list[str],
    centers: dict[str, np.ndarray],
    *,
    radius: float,
) -> list[tuple[str, int, int, float]]:
    """Atom and residue neighbour counts within the radius, plus atoms per cubic angstrom."""

    volume = 4.0 / 3.0 * np.pi * radius**3
    result: list[tuple[str, int, int, float]] = []
    for label in labels:
        center = centers[label]
        deltas = coords - center
        distances = np.sqrt(np.sum(deltas * deltas, axis=1))
        inside = distances <= radius
        neighbours = {labels[index] for index in np.flatnonzero(inside)}
        n_atoms = int(inside.sum())
        result.append((label, n_atoms, len(neighbours), n_atoms / volume))
    return result


class StructurePackingDensityStep(Step):
    """Per-residue local packing density of heavy atoms."""

    provider = "operon-core"

    parameters_file = "structure_packing_density.StructurePackingDensityStep.parameters.json"


    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_packing_density",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure packing density",
        "description": (
            "Measure how tightly each residue is packed: heavy-atom neighbours inside a sphere "
            "around the residue centre, the number of distinct neighbour residues, and atoms "
            "per cubic angstrom."
        ),
        "category": "Machine Learning",
        "icon": "Stack",
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
        "resources": {
            "memory_modes": ["full"],
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        residue_dim = str(params.get("residue_dim", "residue"))
        radius = float(params.get("radius", 6.0))
        exclude = str(params.get("exclude_resnames", "HOH,WAT"))
        output = str(params.get("output", "packing"))

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_packing_density: a PDB form with dims [{atom_dim}, {field_dim}] is "
                f"required, got {list(form.dims)}"
            )
        if not 2.0 <= radius <= 20.0:
            raise StepError(
                "structure_packing_density: radius must be between 2 and 20 angstrom"
            )
        field_columns(form, field_dim, ("x", "y", "z", "chain"))
        coords = atom_coords(form, field_dim)
        mask = heavy_atom_mask(form, field_dim)
        if mask.sum() == 0:
            raise StepError(
                "structure_packing_density: the structure form has no heavy atoms to analyse"
            )
        excluded = {item.strip().upper() for item in exclude.split(",") if item.strip()}
        if has_column(form, field_dim, "resname"):
            resname = np.asarray(
                [str(value).upper() for value in decode_column(form, field_dim, "resname")]
            )
            mask = mask & ~np.isin(resname, list(excluded))
        selected = np.flatnonzero(mask)
        if selected.size == 0:
            raise StepError(
                "structure_packing_density: no heavy atom remains after exclusions"
            )

        labels = [residue_labels(form, field_dim)[index] for index in selected]
        selected_coords = coords[selected]
        names = None
        if has_column(form, field_dim, "atom_name"):
            column = column_index(form, field_dim, "atom_name")
            names = np.asarray(
                [str(value).strip() for value in form.data[selected, column]],
                dtype=object,
            )
        centers = residue_centers(selected_coords, labels, names)
        ordered = residue_order(labels)
        rows = packing_rows(selected_coords, labels, centers, radius=radius)
        by_label = {row[0]: row for row in rows}
        ordered_rows = [by_label[label] for label in ordered if label in by_label]
        ordered_rows.sort(key=lambda row: (-row[3], row[0]))

        data = np.asarray(
            [[float(row[1]), float(row[2]), float(row[3])] for row in ordered_rows],
            dtype=np.float32,
        )
        densities = data[:, 2]
        info = {
            "missing_code": np.nan,
            "radius": radius,
            "n_residues": len(ordered_rows),
            "mean_density": round(float(densities.mean()), 6),
            "median_density": round(float(np.median(densities)), 6),
            "max_density": round(float(densities.max()), 6),
            "min_density": round(float(densities.min()), 6),
            "densest_residue": ordered_rows[0][0],
            "loosest_residue": ordered_rows[-1][0],
            "unit": "atoms/A^3",
        }
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {row[0]: index for index, row in enumerate(ordered_rows)},
                "statistic": {
                    "n_neighbor_atoms": 0,
                    "n_neighbor_residues": 1,
                    "packing_density": 2,
                },
            },
            info=info,
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_residues": len(ordered_rows),
            "radius": radius,
            "mean_density": info["mean_density"],
            "densest_residue": info["densest_residue"],
            "loosest_residue": info["loosest_residue"],
            "residues": [row[0] for row in ordered_rows],
        }
        print(
            f"[structure_packing_density] residues={len(ordered_rows)} radius={radius} "
            f"mean={info['mean_density']:.4f} atoms/A^3"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


__all__ = ["StructurePackingDensityStep", "packing_rows", "residue_centers"]
