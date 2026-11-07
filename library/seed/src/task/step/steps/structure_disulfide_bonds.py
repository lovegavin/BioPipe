"""Disulfide bonds between cysteine sulphur atoms."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from ._protein_common import column_index, decode_column, has_column

_STATISTICS = ("distance",)


def disulfide_pairs(
    coordinates: np.ndarray,
    labels: np.ndarray,
    max_distance: float,
) -> list[dict]:
    """Return SG-SG pairs closer than ``max_distance`` angstrom."""
    pairs: list[dict] = []
    for first in range(len(coordinates)):
        for second in range(first + 1, len(coordinates)):
            distance = float(
                np.linalg.norm(coordinates[first] - coordinates[second])
            )
            if distance > max_distance:
                continue
            left = str(labels[first])
            right = str(labels[second])
            pair = tuple(sorted((left, right)))
            pairs.append(
                {
                    "bond": f"{pair[0]}-{pair[1]}",
                    "distance": distance,
                }
            )
    return sorted(pairs, key=lambda row: (row["distance"], row["bond"]))


class StructureDisulfideBondsStep(Step):
    provider = "operon-core"
    parameters_file = "structure_disulfide_bonds.StructureDisulfideBondsStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_disulfide_bonds",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure disulfide bonds",
        "category": "Machine Learning",
        "icon": "Unite",
        "description": (
            "Detect disulfide bonds from cysteine SG atoms and report the "
            "bonded and free cysteine residues."
        ),
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
                    "info": {"missing_code": {"type": ["number", "null"]}},
                }
            ],
            "output": {
                "version": 1,
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
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
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        out_name = params["output"]
        raw_distance = params.get("max_distance")
        max_distance = 2.5 if raw_distance is None else float(raw_distance)
        if not 1.5 <= max_distance <= 4.0:
            raise StepError(
                "structure_disulfide_bonds: max_distance must be between 1.5 and 4.0 angstrom"
            )
        if not inputs:
            raise StepError("structure_disulfide_bonds: a PDB form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_disulfide_bonds: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        for name in ("x", "y", "z", "resname", "atom_name"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"structure_disulfide_bonds: the PDB form has no '{name}' column"
                )
        resnames = decode_column(form, field_dim, "resname")
        atom_names = decode_column(form, field_dim, "atom_name")
        labels = None
        if has_column(form, field_dim, "chain") and has_column(
            form, field_dim, "residue_number"
        ):
            chains = decode_column(form, field_dim, "chain")
            numbers = decode_column(form, field_dim, "residue_number")
            labels = np.array(
                [f"{chains[i]}:{resnames[i]}:{numbers[i]}" for i in range(len(resnames))],
                dtype=object,
            )
        else:
            raise StepError(
                "structure_disulfide_bonds: the PDB form needs 'chain' and "
                "'residue_number' columns"
            )
        cysteines = {
            str(labels[index])
            for index in range(len(resnames))
            if str(resnames[index]).upper() == "CYS"
        }
        sulphur = np.array(
            [
                str(resnames[index]).upper() == "CYS"
                and str(atom_names[index]).upper() == "SG"
                for index in range(len(resnames))
            ],
            dtype=bool,
        )
        if not sulphur.any():
            raise StepError(
                "structure_disulfide_bonds: the structure form has no cysteine SG atoms"
            )
        coordinates = np.asarray(
            [
                [
                    np.asarray(form.data, dtype=np.float64)[index, column_index(form, field_dim, axis)]
                    for axis in ("x", "y", "z")
                ]
                for index in np.flatnonzero(sulphur)
            ]
        )
        sulphur_labels = labels[sulphur]
        if not np.isfinite(coordinates).all():
            raise StepError(
                "structure_disulfide_bonds: the cysteine SG coordinates are not finite"
            )
        pairs = disulfide_pairs(coordinates, sulphur_labels, max_distance)
        bonded = {
            label
            for pair in pairs
            for label in pair["bond"].split("-")
        }
        free = sorted(cysteines - bonded)
        data = np.asarray([[pair["distance"] for pair in pairs]], dtype=np.float32).reshape(
            len(pairs), 1
        )
        labels_out = {
            "bond": {pair["bond"]: index for index, pair in enumerate(pairs)},
            "statistic": {name: index for index, name in enumerate(_STATISTICS)},
        }
        output = Form(
            data=data,
            dims=["bond", "statistic"],
            labels=labels_out,
            info={
                "missing_code": np.nan,
                "bonds": [
                    {
                        "bond": pair["bond"],
                        "distance": pair["distance"],
                    }
                    for pair in pairs
                ],
                "n_bonds": len(pairs),
                "n_cysteines": len(cysteines),
                "free_cysteines": free,
                "cysteines": sorted(cysteines),
                "max_distance": max_distance,
                "unit": "A",
            },
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_bonds": len(pairs),
            "n_cysteines": len(cysteines),
            "free_cysteines": free,
            "max_distance": max_distance,
        }
        print(
            f"[structure_disulfide_bonds] {len(pairs)} bond(s) among "
            f"{len(cysteines)} cysteine(s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
