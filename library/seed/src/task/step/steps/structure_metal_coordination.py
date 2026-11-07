"""Metal-ion coordination shells from a full-atom structure."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import heavy_atom_mask

METALS = {"ZN", "MG", "MN", "FE", "CA", "CU", "CO", "NI", "NA", "K", "CD", "HG"}
STATISTICS = ("n_ligands", "mean_distance", "n_oxygen", "n_nitrogen", "n_sulfur")


def _fields(form: Form, field_dim: str) -> list[str]:
    return [str(name) for name in form.labels.get(field_dim, {})]


def _column(form: Form, field_dim: str, name: str) -> np.ndarray:
    fields = _fields(form, field_dim)
    if name not in fields:
        raise StepError(f"structure_metal_coordination: the structure form has no '{name}' column")
    axis = 0 if list(form.dims).index(field_dim) == 0 else 1
    return form.data.take(fields.index(name), axis=axis)


def _text(form: Form, field_dim: str, name: str) -> list[str]:
    column = _column(form, field_dim, name)
    decoder = (form.info or {}).get("encoders", {}).get(field_dim, {}).get(name)
    if decoder is not None:
        return [str(decoder.inverse_transform([float(value)])[0]) for value in column]
    return [str(int(value)) if float(value).is_integer() else f"{float(value):g}" for value in column]


def coordination_shell(ions, ligands, ion_coords, ligand_coords, cutoff: float) -> list[dict]:
    tree = cKDTree(ligand_coords)
    rows = []
    for position in ions:
        neighbours = tree.query_ball_point(ion_coords[position], cutoff)
        if not neighbours:
            continue
        distances = [float(np.linalg.norm(ion_coords[position] - ligand_coords[index])) for index in neighbours]
        elements = [ligands[index][0] for index in neighbours]
        rows.append({
            "_ion": position,
            "n_ligands": float(len(neighbours)),
            "mean_distance": float(np.mean(distances)),
            "n_oxygen": float(sum(1 for element in elements if element == "O")),
            "n_nitrogen": float(sum(1 for element in elements if element == "N")),
            "n_sulfur": float(sum(1 for element in elements if element == "S")),
            "_ligands": [ligands[index][1] for index in neighbours],
            "_distances": distances,
        })
    return rows


class StructureMetalCoordinationStep(Step):
    provider = "operon-core"
    parameters_file = "structure_metal_coordination.StructureMetalCoordinationStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_metal_coordination",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Metal coordination shells",
        "description": "Reports coordinating atoms within a distance cutoff of each metal ion.",
        "category": "Machine Learning",
        "icon": "CirclesThree",
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
        ion_dim = str(params.get("ion_dim") or "metal")
        cutoff = float(params.get("cutoff", 2.8))
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_metal_coordination: a PDB form with dims [{atom_dim}, {field_dim}] "
                f"is required, got {list(form.dims)}"
            )
        if not 1.5 <= cutoff <= 4.0:
            raise StepError("structure_metal_coordination: cutoff must be between 1.5 and 4.0 angstrom")

        elements = [str(value).strip().upper() for value in _text(form, field_dim, "element")]
        resnames = [str(value).strip().upper() for value in _text(form, field_dim, "resname")]
        chains = _text(form, field_dim, "chain")
        numbers = _text(form, field_dim, "residue_number")
        atom_names = [str(value).strip() for value in _text(form, field_dim, "atom_name")] if "atom_name" in _fields(form, field_dim) else [""] * len(elements)
        coords = np.column_stack([
            _column(form, field_dim, name).astype(np.float64) for name in ("x", "y", "z")
        ])
        heavy = heavy_atom_mask(form, field_dim)

        ion_positions = [
            index for index, (element, resname) in enumerate(zip(elements, resnames))
            if element in METALS or resname in METALS
        ]
        if not ion_positions:
            raise StepError(
                "structure_metal_coordination: no metal ion (Zn, Mg, Mn, Fe, Ca, Cu, Co, Ni, Na, K, Cd, Hg) "
                "was found in the structure form"
            )

        ligand_positions = [
            index for index in range(len(elements))
            if index not in ion_positions and heavy[index]
        ]
        ligands = [
            (elements[index], f"{chains[index]}:{resnames[index]}:{numbers[index]}:{atom_names[index]}".strip(":"))
            for index in ligand_positions
        ]
        rows = coordination_shell(
            ion_positions, ligands, coords, coords[ligand_positions], cutoff
        )
        if not rows:
            raise StepError("structure_metal_coordination: no ligand atom is within the cutoff of a metal ion")

        row_labels = []
        labels = {}
        for row in rows:
            ion = int(row["_ion"])
            base = f"{chains[ion]}:{resnames[ion]}:{numbers[ion]}"
            label = base
            suffix = 1
            while label in labels:
                label = f"{base}#{suffix}"
                suffix += 1
            row_labels.append((label, ion))
            labels[label] = len(row_labels) - 1
        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        output = Form(
            data=data,
            dims=[ion_dim, "statistic"],
            labels={ion_dim: {label: index for index, (label, _) in enumerate(row_labels)},
                    "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "cutoff": cutoff,
                "n_ions": len(rows),
                "shells": [
                    {"label": label, "ligands": row["_ligands"],
                     "distances": [round(value, 3) for value in row["_distances"]]}
                    for (label, _), row in zip(row_labels, rows)
                ],
                "unit": "angstrom",
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_ions": len(rows),
            "cutoff": cutoff,
            "mean_coordination": float(np.mean([row["n_ligands"] for row in rows])),
        }
        print(
            f"[structure_metal_coordination] {len(rows)} ion shells at cutoff {cutoff} A, "
            f"mean coordination {self._export_data['mean_coordination']:.2f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
