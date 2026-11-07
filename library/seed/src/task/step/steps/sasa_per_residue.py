"""Per-residue solvent-accessible surface area with Shrake-Rupley sampling."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import decode_column, heavy_atom_mask, residue_labels
from .interface_bsa import sasa_per_atom, vdw_radii

_STATISTICS = ("sasa", "sasa_fraction", "n_atoms")


def residue_sasa(
    coords: np.ndarray,
    radii: np.ndarray,
    labels: np.ndarray,
    *,
    probe_radius: float = 1.4,
    n_points: int = 92,
) -> list[tuple[str, float, int]]:
    """Aggregate atom SASA into ``(label, area, n_atoms)`` in first-appearance order."""
    atom_areas = sasa_per_atom(coords, radii, probe_radius=probe_radius, n_points=n_points)
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    order: list[str] = []
    for label, area in zip(labels, atom_areas):
        key = str(label)
        if key not in totals:
            totals[key] = 0.0
            counts[key] = 0
            order.append(key)
        totals[key] += float(area)
        counts[key] += 1
    return [(key, totals[key], counts[key]) for key in order]


class SasaPerResidueStep(Step):
    """Compute Shrake-Rupley SASA for every residue of a structure."""

    provider = "operon-core"
    parameters_file = "sasa_per_residue.SasaPerResidueStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sasa_per_residue",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Per-Residue SASA",
        "description": (
            "Compute the Shrake-Rupley solvent-accessible surface area of every residue in a "
            "full-atom structure with Bondi van der Waals radii and a 1.4 A probe."
        ),
        "category": "Machine Learning",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "structure",
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) != 1:
            raise StepError("sasa_per_residue: exactly one structure form is required")
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim", "atom"))
        field_dim = str(ctx.step_params.get("field_dim", "field"))
        residue_dim = str(ctx.step_params.get("residue_dim", "residue"))
        probe_radius = float(ctx.step_params.get("probe_radius", 1.4))
        n_points = int(ctx.step_params.get("n_points", 92))
        exclude_text = str(ctx.step_params.get("exclude_resnames", "HOH,WAT"))
        output_name = str(ctx.step_params.get("output", "sasa"))
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "sasa_per_residue: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        if not 1.0 <= probe_radius <= 3.0:
            raise StepError("sasa_per_residue: probe_radius must be between 1.0 and 3.0")
        if not 32 <= n_points <= 1024:
            raise StepError("sasa_per_residue: n_points must be between 32 and 1024")
        resname = decode_column(form, field_dim, "resname")
        if resname is None:
            raise StepError("sasa_per_residue: the structure form has no 'resname' column")
        element = decode_column(form, field_dim, "element")
        if element is None:
            raise StepError("sasa_per_residue: the structure form has no 'element' column")
        excluded = {
            item.strip().upper() for item in exclude_text.split(",") if item.strip()
        }
        heavy = heavy_atom_mask(form, field_dim)
        resnames = np.array([str(value).strip().upper() for value in resname])
        keep = heavy & ~np.isin(resnames, sorted(excluded))
        if not keep.any():
            raise StepError("sasa_per_residue: the structure has no heavy atoms to analyse")
        columns = []
        for name in ("x", "y", "z"):
            index = _column(form, field_dim, name)
            if index is None:
                raise StepError(f"sasa_per_residue: the structure form has no '{name}' column")
            columns.append(form.data[:, index])
        coords = np.column_stack(columns)[keep]
        radii = vdw_radii(element[keep])
        labels = residue_labels(form, field_dim)[keep]
        residues = residue_sasa(
            coords, radii, labels, probe_radius=probe_radius, n_points=n_points
        )
        total = sum(area for _, area, _ in residues)
        values = np.array(
            [
                [
                    area,
                    (area / total) if total > 0 else 0.0,
                    float(count),
                ]
                for _, area, count in residues
            ],
            dtype=np.float32,
        )
        output = Form(
            data=values,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, (label, _, _) in enumerate(residues)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "probe_radius": probe_radius,
                "n_points": n_points,
                "excluded_resnames": sorted(excluded),
                "total_sasa": round(float(total), 4),
                "n_residues": len(residues),
                "unit": "A^2",
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_residues": len(residues),
            "total_sasa": round(float(total), 4),
            "probe_radius": probe_radius,
            "n_points": n_points,
            "largest_residues": [
                {"residue": label, "sasa": round(area, 4)}
                for label, area, _ in sorted(residues, key=lambda item: -item[1])[:5]
            ],
        }
        print(
            f"[sasa_per_residue] {len(residues)} residues, total {total:.1f} A^2"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _column(form: Form, field_dim: str, name: str) -> int | None:
    from ._protein_common import column_index

    return column_index(form, field_dim, name)
