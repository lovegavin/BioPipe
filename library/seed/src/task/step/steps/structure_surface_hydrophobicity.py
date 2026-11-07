"""Per-residue surface hydrophobicity from solvent-accessible area."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import heavy_atom_mask
from src.task.step.steps.interface_bsa import sasa_per_atom, vdw_radii

KD = {
    "ALA": 1.8, "ARG": -4.5, "ASN": -3.5, "ASP": -3.5, "CYS": 2.5,
    "GLN": -3.5, "GLU": -3.5, "GLY": -0.4, "HIS": -3.2, "ILE": 4.5,
    "LEU": 3.8, "LYS": -3.9, "MET": 1.9, "PHE": 2.8, "PRO": -1.6,
    "SER": -0.8, "THR": -0.7, "TRP": -0.9, "TYR": -1.3, "VAL": 4.2,
}

STATISTICS = ("sasa", "sasa_fraction", "hydrophobicity", "hydrophobic_sasa")


def _fields(form: Form, field_dim: str) -> list[str]:
    return [str(name) for name in form.labels.get(field_dim, {})]


def _column(form: Form, field_dim: str, name: str) -> np.ndarray:
    fields = _fields(form, field_dim)
    if name not in fields:
        raise StepError(f"structure_surface_hydrophobicity: the structure form has no '{name}' column")
    axis = 0 if list(form.dims).index(field_dim) == 0 else 1
    return form.data.take(fields.index(name), axis=axis)


def _text(form: Form, field_dim: str, name: str) -> list[str]:
    column = _column(form, field_dim, name)
    decoder = (form.info or {}).get("encoders", {}).get(field_dim, {}).get(name)
    if decoder is not None:
        return [str(decoder.inverse_transform([float(value)])[0]) for value in column]
    return [str(int(value)) if float(value).is_integer() else f"{float(value):g}" for value in column]


class StructureSurfaceHydrophobicityStep(Step):
    provider = "operon-core"
    parameters_file = "structure_surface_hydrophobicity.StructureSurfaceHydrophobicityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_surface_hydrophobicity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Per-residue surface hydrophobicity",
        "description": "Multiplies per-residue solvent-accessible area by the Kyte-Doolittle scale.",
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
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
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
        probe_radius = float(params.get("probe_radius", 1.4))
        n_points = int(params.get("n_points", 92))
        exclude = [
            item.strip().upper()
            for item in str(params.get("exclude_resnames", "HOH,WAT")).split(",")
            if item.strip()
        ]
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_surface_hydrophobicity: a PDB form with dims [{atom_dim}, {field_dim}] "
                f"is required, got {list(form.dims)}"
            )
        if not 1.0 <= probe_radius <= 3.0:
            raise StepError("structure_surface_hydrophobicity: probe_radius must be between 1.0 and 3.0")
        if not 32 <= n_points <= 1024:
            raise StepError("structure_surface_hydrophobicity: n_points must be between 32 and 1024")

        for name in ("x", "y", "z", "resname", "chain", "residue_number", "element"):
            if name not in _fields(form, field_dim):
                raise StepError(
                    f"structure_surface_hydrophobicity: the structure form has no '{name}' column"
                )

        resname = [value.strip().upper() for value in _text(form, field_dim, "resname")]
        keep = heavy_atom_mask(form, field_dim) & np.asarray(
            [value not in exclude for value in resname]
        )
        if not np.any(keep):
            raise StepError("structure_surface_hydrophobicity: the structure has no heavy atoms to analyse")

        index = np.where(keep)[0]
        coords = np.column_stack([
            _column(form, field_dim, name).astype(np.float64)[index] for name in ("x", "y", "z")
        ])
        elements = [str(value).strip().upper() for value in _text(form, field_dim, "element")]
        radii = vdw_radii([elements[position] for position in index])
        areas = sasa_per_atom(coords, radii, probe_radius=probe_radius, n_points=n_points)

        chains = _text(form, field_dim, "chain")
        numbers = _text(form, field_dim, "residue_number")
        icodes = ["_"] * len(chains)
        if "insertion_code" in _fields(form, field_dim):
            icodes = _text(form, field_dim, "insertion_code")
        suffix = ["" if code in ("_", "") else code for code in icodes]

        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        areas_max: dict[str, float] = {}
        order: list[str] = []
        for position, area in zip(index, areas):
            label = f"{chains[position]}:{resname[position]}:{numbers[position]}{suffix[position]}"
            if label not in totals:
                totals[label] = 0.0
                counts[label] = 0
                areas_max[label] = 0.0
                order.append(label)
            totals[label] += float(area)
            counts[label] += 1
            areas_max[label] += float(4.0 * np.pi * (radii[list(index).index(position)] + probe_radius) ** 2)

        rows = []
        for label in order:
            name = label.split(":")[1]
            scale = KD.get(name, 0.0)
            sasa = totals[label]
            fraction = sasa / max(areas_max[label], 1e-9)
            rows.append((label, sasa, min(fraction, 1.0), scale, sasa * scale))
        rows.sort(key=lambda row: (-row[1] * abs(row[3]), row[0]))

        data = np.asarray([[row[1], row[2], row[3], row[4]] for row in rows], dtype=np.float32)
        total = float(np.sum(data[:, 0]))
        hydrophobic = float(np.sum(data[np.asarray(data[:, 3]) > 0.0, 0]))
        output = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {row[0]: position for position, row in enumerate(rows)},
                "statistic": {name: position for position, name in enumerate(STATISTICS)},
            },
            info={
                "missing_code": float("nan"),
                "probe_radius": probe_radius,
                "n_points": n_points,
                "total_sasa": total,
                "hydrophobic_sasa": hydrophobic,
                "hydrophobic_fraction": float(hydrophobic / max(total, 1e-9)),
                "excluded_resnames": exclude,
                "unit": "A^2",
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_residues": len(rows),
            "total_sasa": total,
            "hydrophobic_sasa": hydrophobic,
            "hydrophobic_fraction": output.info["hydrophobic_fraction"],
        }
        print(
            f"[structure_surface_hydrophobicity] {len(rows)} residues, total {total:.2f} A^2, "
            f"hydrophobic fraction {output.info['hydrophobic_fraction']:.3f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
