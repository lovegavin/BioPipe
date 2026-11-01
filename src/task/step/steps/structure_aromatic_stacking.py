"""Aromatic stacking (pi-pi) pairs between aromatic side chains."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import column_index, decode_column, residue_labels
from ._ring_geometry import require_form, ring_planes

_STATISTICS = ("distance", "angle_deg", "offset_a", "offset_b", "parallel")


def stacking_pairs(
    rings: list[dict],
    *,
    max_distance: float = 6.5,
    max_offset: float = 2.0,
    parallel_angle: float = 30.0,
) -> list[dict]:
    """Classify ring pairs as parallel, T-shaped or other."""
    rows: list[dict] = []
    for first_index in range(len(rings)):
        first = rings[first_index]
        for second_index in range(first_index + 1, len(rings)):
            second = rings[second_index]
            if first["label"] == second["label"]:
                continue
            delta = second["centroid"] - first["centroid"]
            distance = float(np.linalg.norm(delta))
            if distance > max_distance:
                continue
            angle = float(
                np.degrees(
                    np.arccos(
                        float(
                            np.clip(
                                abs(np.dot(first["normal"], second["normal"])), 0.0, 1.0
                            )
                        )
                    )
                )
            )
            offset_a = float(abs(np.dot(second["centroid"] - first["centroid"], first["normal"])))
            offset_b = float(abs(np.dot(first["centroid"] - second["centroid"], second["normal"])))
            if angle <= parallel_angle and max(offset_a, offset_b) <= max_offset:
                kind = "parallel"
            elif angle >= 60.0 and min(offset_a, offset_b) <= max_offset:
                kind = "t_shaped"
            else:
                kind = "other"
            rows.append(
                {
                    "bond": f"{first['label']}-{second['label']}",
                    "first": first["label"],
                    "second": second["label"],
                    "distance": distance,
                    "angle_deg": angle,
                    "offset_a": offset_a,
                    "offset_b": offset_b,
                    "parallel": 1.0 if kind == "parallel" else 0.0,
                    "kind": kind,
                }
            )
    rows.sort(key=lambda row: (-round(row["distance"], 6), row["bond"]))
    return rows


class StructureAromaticStackingStep(Step):
    provider = "biopipe-core"
    parameters_file = (
        "structure_aromatic_stacking.StructureAromaticStackingStep.parameters.json"
    )
    definition = {
        "protocol_version": 3,
        "id": "structure_aromatic_stacking",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Aromatic stacking",
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
        require_form(form, atom_dim, field_dim, "structure_aromatic_stacking")
        raw_distance = params.get("max_distance")
        max_distance = 6.5 if raw_distance is None else float(raw_distance)
        if not 3.0 <= max_distance <= 10.0:
            raise StepError(
                "structure_aromatic_stacking: max_distance must be between 3.0 and 10.0 angstrom"
            )
        raw_offset = params.get("max_offset")
        max_offset = 2.0 if raw_offset is None else float(raw_offset)
        if not 0.0 < max_offset <= 5.0:
            raise StepError(
                "structure_aromatic_stacking: max_offset must be between 0 and 5.0 angstrom"
            )
        raw_angle = params.get("parallel_angle")
        parallel_angle = 30.0 if raw_angle is None else float(raw_angle)
        if not 0.0 < parallel_angle <= 90.0:
            raise StepError(
                "structure_aromatic_stacking: parallel_angle must be between 0 and 90 degrees"
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
                "structure_aromatic_stacking: the PDB form needs 'resname' and 'atom_name' columns"
            )
        labels = residue_labels(form, field_dim)
        rings = ring_planes(coordinates, resnames, atom_names, labels)
        if len(rings) < 2:
            raise StepError(
                "structure_aromatic_stacking: at least two aromatic rings are required"
            )
        rows = stacking_pairs(
            rings,
            max_distance=max_distance,
            max_offset=max_offset,
            parallel_angle=parallel_angle,
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
                "n_rings": len(rings),
                "n_pairs": len(rows),
                "parallel": sum(1 for row in rows if row["kind"] == "parallel"),
                "t_shaped": sum(1 for row in rows if row["kind"] == "t_shaped"),
                "other": sum(1 for row in rows if row["kind"] == "other"),
                "pairs": rows,
                "max_distance": max_distance,
                "max_offset": max_offset,
                "parallel_angle": parallel_angle,
                "unit": "A",
            },
        )
        form_out.validate()
        ctx[out_name] = form_out
        self._export_data = {
            "n_rings": len(rings),
            "n_pairs": len(rows),
            "parallel": sum(1 for row in rows if row["kind"] == "parallel"),
            "t_shaped": sum(1 for row in rows if row["kind"] == "t_shaped"),
        }
        print(
            f"[structure_aromatic_stacking] {len(rows)} ring pair(s) among "
            f"{len(rings)} rings"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
