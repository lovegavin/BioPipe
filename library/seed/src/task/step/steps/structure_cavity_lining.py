"""Residues lining the largest buried cavity of a PDB structure form.

The structure is rasterised onto a regular grid (see ``structure_cavity_scan``);
free cells unreachable from the box boundary form buried cavities.  The largest
cavity by volume is selected and every residue with a heavy atom within
``lining_cutoff`` of a cavity cell centre is reported.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    heavy_atom_mask,
    residue_labels,
    residue_order,
)
from src.task.step.steps.interface_bsa import vdw_radii
from src.task.step.steps.structure_cavity_scan import (
    cavity_components,
    cell_centres,
    free_mask,
    grid_shape,
    outside_mask,
)

_STATISTICS = ("min_distance", "n_atoms")
_REQUIRED = ("x", "y", "z", "element")


def cavity_cells(
    coords: np.ndarray,
    radii: np.ndarray,
    *,
    spacing: float,
    probe_radius: float,
    padding: float,
) -> tuple[list[list[tuple[int, int, int]]], np.ndarray, tuple[int, int, int], np.ndarray]:
    """Buried cavity components, their centres, the grid shape and the grid origin."""

    lo = coords.min(axis=0) - padding
    hi = coords.max(axis=0) + padding
    shape = grid_shape(lo, hi, spacing)
    centres = cell_centres(lo, shape, spacing)
    free = free_mask(centres, shape, coords, radii, probe_radius).reshape(shape)
    accessible = outside_mask(free, shape)
    components = cavity_components(free & ~accessible, shape)
    return components, centres, shape, lo


def lining_rows(
    residue_coords: dict[str, np.ndarray],
    centres: np.ndarray,
    *,
    cutoff: float,
) -> list[tuple[str, float, int]]:
    """Residues with a heavy atom within ``cutoff`` of a cavity cell centre."""

    from scipy.spatial import cKDTree

    tree = cKDTree(centres)
    rows: list[tuple[str, float, int]] = []
    for label, atoms in residue_coords.items():
        distance, _ = tree.query(atoms, k=1)
        nearest = float(distance.min()) if distance.size else float("inf")
        if nearest > cutoff:
            continue
        rows.append((label, nearest, int((distance <= cutoff).sum())))
    rows.sort(key=lambda row: (row[1], row[0]))
    return rows


class StructureCavityLiningStep(Step):
    provider = "operon-core"
    parameters_file = "structure_cavity_lining.StructureCavityLiningStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_cavity_lining",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Cavity lining residues",
        "description": (
            "Residues lining the largest buried cavity of a structure, with "
            "their nearest distance to the cavity volume."
        ),
        "category": "Structure",
        "icon": "Cube",
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
                    "info": {"encoders": {"type": "object", "optional": True}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
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
        if not inputs:
            raise StepError("structure_cavity_lining: a PDB atom form input is required")
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        residue_dim = str(params.get("residue_dim") or "residue")
        out_name = str(params.get("output") or "lining")

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_cavity_lining: expected a PDB atom table with dims "
                f"[{atom_dim}, {field_dim}], got {list(form.dims)}"
            )
        fields = form.labels[field_dim]
        for name in _REQUIRED:
            if name not in fields:
                raise StepError(f"structure_cavity_lining: the structure form has no '{name}' column")

        spacing = float(params.get("spacing") if params.get("spacing") is not None else 1.0)
        probe_radius = float(
            params.get("probe_radius") if params.get("probe_radius") is not None else 1.4
        )
        min_volume = float(params.get("min_volume") if params.get("min_volume") is not None else 20.0)
        padding = float(params.get("padding") if params.get("padding") is not None else 2.0)
        cutoff = float(params.get("lining_cutoff") if params.get("lining_cutoff") is not None else 4.0)

        if not 0.5 <= spacing <= 4.0:
            raise StepError("structure_cavity_lining: spacing must be in [0.5, 4.0]")
        if not 0.5 <= probe_radius <= 5.0:
            raise StepError("structure_cavity_lining: probe_radius must be in [0.5, 5.0]")
        if min_volume < 0.0:
            raise StepError("structure_cavity_lining: min_volume must be non-negative")
        if not 0.0 <= padding <= 10.0:
            raise StepError("structure_cavity_lining: padding must be in [0, 10]")
        if not 0.5 <= cutoff <= 12.0:
            raise StepError("structure_cavity_lining: lining_cutoff must be in [0.5, 12.0]")

        mask = heavy_atom_mask(form, field_dim)
        if not mask.any():
            raise StepError("structure_cavity_lining: the structure form has no heavy atoms")
        xyz = np.column_stack(
            [np.asarray(form.data[mask, column_index(form, field_dim, axis)], dtype=np.float64) for axis in ("x", "y", "z")]
        )
        elements = decode_column(form, field_dim, "element")
        if elements is None:
            raise StepError("structure_cavity_lining: the structure form has no 'element' column")
        radii = vdw_radii(elements[mask])
        labels = residue_labels(form, field_dim)[mask]

        components, centres, shape, lo = cavity_cells(
            xyz, radii, spacing=spacing, probe_radius=probe_radius, padding=padding
        )
        if not components:
            raise StepError("structure_cavity_lining: no buried cavity was found")

        nx, ny, nz = shape
        best = None
        best_volume = 0.0
        for cells in components:
            volume = len(cells) * spacing**3
            if volume < min_volume:
                continue
            if volume > best_volume:
                best = cells
                best_volume = volume
        if best is None:
            raise StepError(
                "structure_cavity_lining: no cavity reaches min_volume "
                f"{min_volume} A^3 (largest {max(len(c) for c in components) * spacing**3:.1f})"
            )

        flat = np.array([x * ny * nz + y * nz + z for x, y, z in best], dtype=np.int64)
        cavity_centres = centres[flat]
        centroid = cavity_centres.mean(axis=0)

        residue_coords: dict[str, np.ndarray] = {
            str(label): xyz[labels == label] for label in residue_order(labels)
        }

        rows = lining_rows(residue_coords, cavity_centres, cutoff=cutoff)
        if not rows:
            raise StepError(
                "structure_cavity_lining: no residue lies within "
                f"{cutoff} A of the largest cavity"
            )

        data = np.asarray([[row[1], float(row[2])] for row in rows], dtype=np.float32)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {row[0]: position for position, row in enumerate(rows)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_residues": len(rows),
                "cavity_volume": best_volume,
                "n_cells": len(best),
                "n_cavities": len(components),
                "grid_shape": [int(value) for value in shape],
                "grid_origin": [float(value) for value in lo],
                "centroid": [float(value) for value in centroid],
                "spacing": spacing,
                "probe_radius": probe_radius,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_residues": len(rows),
            "cavity_volume": best_volume,
            "n_cells": len(best),
            "n_cavities": len(components),
        }
        print(
            f"[structure_cavity_lining] {len(rows)} residues line a "
            f"{best_volume:.1f} A^3 cavity"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
