"""Cation-pi interactions between charged side chains and aromatic rings."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import column_index, decode_column, residue_labels
from ._ring_geometry import cation_centroids, require_form, ring_planes

_STATISTICS = ("distance", "offset")


def cation_pi_bonds(
    rings: list[dict],
    cations: list[dict],
    *,
    max_distance: float = 6.0,
    max_offset: float = 2.0,
) -> list[dict]:
    """Pair charged cations with aromatic ring planes."""
    rows: list[dict] = []
    for cation in cations:
        centre = cation["centroid"]
        for ring in rings:
            delta = ring["centroid"] - centre
            distance = float(np.linalg.norm(delta))
            if distance > max_distance:
                continue
            offset = float(abs(np.dot(centre - ring["centroid"], ring["normal"])))
            if offset > max_offset:
                continue
            rows.append(
                {
                    "bond": f"{cation['label']}-{ring['label']}",
                    "cation": cation["label"],
                    "ring": ring["label"],
                    "ring_index": ring["ring_index"],
                    "distance": distance,
                    "offset": offset,
                }
            )
    rows.sort(key=lambda row: (-round(row["distance"], 6), row["bond"]))
    return rows


class StructureCationPiStep(Step):
    provider = "operon-core"
    parameters_file = "structure_cation_pi.StructureCationPiStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_cation_pi",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Cation-pi interactions",
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
        require_form(form, atom_dim, field_dim, "structure_cation_pi")
        raw_distance = params.get("max_distance")
        max_distance = 6.0 if raw_distance is None else float(raw_distance)
        if not 2.0 <= max_distance <= 10.0:
            raise StepError(
                "structure_cation_pi: max_distance must be between 2.0 and 10.0 angstrom"
            )
        raw_offset = params.get("max_offset")
        max_offset = 2.0 if raw_offset is None else float(raw_offset)
        if not 0.0 < max_offset <= 5.0:
            raise StepError(
                "structure_cation_pi: max_offset must be between 0 and 5.0 angstrom"
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
        resnames = decode_column(form, field_dim, "resname")
        atom_names = decode_column(form, field_dim, "atom_name")
        if resnames is None or atom_names is None:
            raise StepError(
                "structure_cation_pi: the PDB form needs 'resname' and 'atom_name' columns"
            )
        labels = residue_labels(form, field_dim)
        rings = ring_planes(coordinates, resnames, atom_names, labels)
        if not rings:
            raise StepError(
                "structure_cation_pi: the structure form has no aromatic ring atoms "
                "(PHE, TYR, TRP, HIS)"
            )
        cations = cation_centroids(coordinates, resnames, atom_names, labels)
        if not cations:
            raise StepError(
                "structure_cation_pi: no charged cations (LYS, ARG, HIS) were found in the structure form"
            )
        rows = cation_pi_bonds(
            rings, cations, max_distance=max_distance, max_offset=max_offset
        )
        data = (
            np.asarray([[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32)
            if rows
            else np.zeros((0, len(_STATISTICS)), dtype=np.float32)
        )
        bond_dim = str(params.get("bond_dim") or "bond")
        out_name = params["output"]
        form_out = Form(
            data=data,
            dims=[bond_dim, "statistic"],
            labels={
                bond_dim: {row["bond"]: index for index, row in enumerate(rows)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_cations": len(cations),
                "n_rings": len(rings),
                "n_bonds": len(rows),
                "bonds": rows,
                "max_distance": max_distance,
                "max_offset": max_offset,
                "unit": "A",
            },
        )
        form_out.validate()
        ctx[out_name] = form_out
        self._export_data = {
            "n_cations": len(cations),
            "n_rings": len(rings),
            "n_bonds": len(rows),
        }
        print(
            f"[structure_cation_pi] {len(rows)} cation-pi bond(s) among "
            f"{len(cations)} cations and {len(rings)} rings"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
