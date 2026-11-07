"""Amide-pi interactions between backbone amides and aromatic rings."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import column_index, decode_column, residue_labels
from ._ring_geometry import (
    amide_groups,
    angle_between,
    require_form,
    ring_planes,
)

_STATISTICS = ("distance", "offset", "angle_deg")


def amide_pi_bonds(
    rings: list[dict],
    amides: list[dict],
    *,
    max_distance: float = 4.5,
    max_offset: float = 2.5,
    min_angle: float = 90.0,
) -> list[dict]:
    """Pair amide carbons with aromatic ring planes."""
    rows: list[dict] = []
    for amide in amides:
        carbon = amide["carbon"]
        direction = amide["n_bond"]
        for ring in rings:
            delta = ring["centroid"] - carbon
            distance = float(np.linalg.norm(delta))
            if distance > max_distance:
                continue
            angle = angle_between(direction, delta)
            if not np.isfinite(angle) or angle < min_angle:
                continue
            offset = float(abs(np.dot(carbon - ring["centroid"], ring["normal"])))
            if offset > max_offset:
                continue
            rows.append(
                {
                    "bond": f"{amide['label']}-{ring['label']}",
                    "donor": amide["label"],
                    "ring": ring["label"],
                    "ring_index": ring["ring_index"],
                    "distance": distance,
                    "offset": offset,
                    "angle_deg": angle,
                }
            )
    rows.sort(key=lambda row: (-round(row["distance"], 6), row["bond"]))
    return rows


class StructureAmidePiBondsStep(Step):
    provider = "operon-core"
    parameters_file = (
        "structure_amide_pi_bonds.StructureAmidePiBondsStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_amide_pi_bonds",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Amide-pi interactions",
        "category": "Machine Learning",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {},
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        form = inputs[0]
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        require_form(form, atom_dim, field_dim, "structure_amide_pi_bonds")
        raw_distance = params.get("max_distance")
        max_distance = 4.5 if raw_distance is None else float(raw_distance)
        if not 2.0 <= max_distance <= 8.0:
            raise StepError(
                "structure_amide_pi_bonds: max_distance must be between 2.0 and 8.0 angstrom"
            )
        raw_offset = params.get("max_offset")
        max_offset = 2.5 if raw_offset is None else float(raw_offset)
        if not 0.0 < max_offset <= 5.0:
            raise StepError(
                "structure_amide_pi_bonds: max_offset must be between 0 and 5.0 angstrom"
            )
        raw_angle = params.get("min_angle")
        min_angle = 90.0 if raw_angle is None else float(raw_angle)
        if not 0.0 <= min_angle <= 180.0:
            raise StepError(
                "structure_amide_pi_bonds: min_angle must be between 0 and 180 degrees"
            )
        coordinates = np.asarray(
            form.data[
                :,
                [
                    column_index(form, field_dim, "x"),
                    column_index(form, field_dim, "y"),
                    column_index(form, field_dim, "z"),
                ],
            ],
            dtype=np.float64,
        )
        if coordinates.size == 0:
            raise StepError("structure_amide_pi_bonds: the structure form has no atoms")
        resnames = decode_column(form, field_dim, "resname")
        atom_names = decode_column(form, field_dim, "atom_name")
        chains = decode_column(form, field_dim, "chain")
        if resnames is None or atom_names is None or chains is None:
            raise StepError(
                "structure_amide_pi_bonds: the PDB form needs 'resname', 'atom_name' and 'chain' columns"
            )
        labels = residue_labels(form, field_dim)
        numbers = np.asarray(
            [round(float(value)) for value in form.data[:, column_index(form, field_dim, "residue_number")]],
            dtype=np.int64,
        )
        rings = ring_planes(coordinates, resnames, atom_names, labels)
        if not rings:
            raise StepError(
                "structure_amide_pi_bonds: the structure form has no aromatic ring atoms "
                "(PHE, TYR, TRP, HIS)"
            )
        amides = amide_groups(coordinates, resnames, atom_names, labels, chains, numbers)
        if not amides:
            raise StepError(
                "structure_amide_pi_bonds: at least two consecutive residues with C, O and N are required"
            )
        rows = amide_pi_bonds(
            rings,
            amides,
            max_distance=max_distance,
            max_offset=max_offset,
            min_angle=min_angle,
        )
        data = (
            np.asarray([[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32)
            if rows
            else np.zeros((0, len(_STATISTICS)), dtype=np.float32)
        )
        residu_dim = str(params.get("bond_dim") or "bond")
        out_name = params["output"]
        form_out = Form(
            data=data,
            dims=[residu_dim, "statistic"],
            labels={
                residu_dim: {row["bond"]: index for index, row in enumerate(rows)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_amides": len(amides),
                "n_rings": len(rings),
                "n_bonds": len(rows),
                "bonds": rows,
                "max_distance": max_distance,
                "max_offset": max_offset,
                "min_angle": min_angle,
                "unit": "A",
            },
        )
        form_out.validate()
        ctx[out_name] = form_out
        self._export_data = {
            "n_amides": len(amides),
            "n_rings": len(rings),
            "n_bonds": len(rows),
            "mean_distance": round(float(np.mean(data[:, 0])), 4) if rows else 0.0,
        }
        print(
            f"[structure_amide_pi_bonds] {len(rows)} amide-pi bond(s) among "
            f"{len(amides)} amides and {len(rings)} rings"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
