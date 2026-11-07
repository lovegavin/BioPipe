"""Secondary-structure element contact network.

Segments come from the same phi/psi assignment as ``structure_secondary_structure``;
every pair of non-coil segments is then scored by its closest CA distance and the
number of residue-residue contacts below the contact cutoff.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, decode_column, has_column, residue_labels
from src.task.step.steps.structure_secondary_structure import (
    assign_states,
    backbone_angles,
    segment_rows,
)

_STATISTICS = ("distance", "n_contacts")
_KINDS = {("H", "H"): "helix-helix", ("E", "E"): "strand-strand", ("H", "E"): "helix-strand"}


def ca_coordinates(form, atom_dim: str, field_dim: str) -> tuple[list[str], np.ndarray]:
    labels = residue_labels(form, field_dim)
    names = decode_column(form, field_dim, "atom_name")
    coords = np.column_stack(
        [np.asarray(form.data[:, column_index(form, field_dim, axis)], dtype=np.float64) for axis in ("x", "y", "z")]
    )
    positions: dict[str, int] = {}
    for index, label in enumerate(labels):
        if str(names[index]).strip().upper() == "CA" and label not in positions:
            positions[label] = index
    ordered = [label for label in dict.fromkeys(labels) if label in positions]
    if len(ordered) < 3:
        raise StepError("structure_ss_bridge_network: at least three CA atoms are required")
    return ordered, coords[[positions[label] for label in ordered]]


def bridge_rows(segments: list[dict], ca: np.ndarray, residue_index: dict[str, int], cutoff: float, contact: float):
    usable = [segment for segment in segments if segment["state"] != "C" and segment["length"] >= 2]
    rows: list[tuple[str, float, float]] = []
    for first, second in combinations(usable, 2):
        indexes_a = [residue_index[label] for label in first["residues"] if label in residue_index]
        indexes_b = [residue_index[label] for label in second["residues"] if label in residue_index]
        if not indexes_a or not indexes_b:
            continue
        points_a = ca[indexes_a]
        points_b = ca[indexes_b]
        distances = np.linalg.norm(points_a[:, None, :] - points_b[None, :, :], axis=2)
        minimum = float(distances.min())
        if minimum > cutoff:
            continue
        contacts = int(np.sum(distances <= contact))
        if first["state"] == "E" and second["state"] == "H":
            first, second = second, first
        kind = _KINDS[(first["state"], second["state"])]
        label = (
            f"{kind}:{first['state']}{first['start']}-{first['end']}/"
            f"{second['state']}{second['start']}-{second['end']}"
        )
        rows.append((label, minimum, float(contacts)))
    rows.sort(key=lambda row: (row[1], row[0]))
    return rows


class StructureSsBridgeNetworkStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ss_bridge_network.StructureSsBridgeNetworkStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ss_bridge_network",
        "version": "1.0.0",
        "kind": "operator",
        "title": "SSE bridge network",
        "description": "Contact network between secondary-structure elements.",
        "category": "Machine Learning",
        "icon": "ShareNetwork",
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
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        bridge_dim = str(params.get("bridge_dim") or "bridge")
        window = int(params.get("window") if params.get("window") is not None else 5)
        cutoff = float(params.get("cutoff") if params.get("cutoff") is not None else 8.0)
        contact = float(params.get("contact") if params.get("contact") is not None else 5.0)
        min_length = int(params.get("min_length") if params.get("min_length") is not None else 2)
        out_name = str(params.get("output") or "bridges")

        if len(inputs) != 1 or list(inputs[0].dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_ss_bridge_network: a structure form with dims "
                f"[{atom_dim}, {field_dim}] is required"
            )
        if not 1 <= window <= 21:
            raise StepError("structure_ss_bridge_network: window must be between 1 and 21 residues")
        if not 1.0 <= cutoff <= 40.0:
            raise StepError("structure_ss_bridge_network: cutoff must be in [1, 40] angstrom")
        if not 1.0 <= contact <= cutoff:
            raise StepError(
                "structure_ss_bridge_network: contact must be in [1, cutoff] angstrom"
            )
        if min_length < 1:
            raise StepError("structure_ss_bridge_network: min_length must be at least 1")

        form = inputs[0]
        for name in ("x", "y", "z", "atom_name"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"structure_ss_bridge_network: the structure form has no '{name}' column"
                )

        labels = residue_labels(form, field_dim)
        names = decode_column(form, field_dim, "atom_name")
        coords = np.column_stack(
            [
                np.asarray(form.data[:, column_index(form, field_dim, axis)], dtype=np.float64)
                for axis in ("x", "y", "z")
            ]
        )
        residues, angles = backbone_angles(coords, labels, names)
        if len(residues) < 3:
            raise StepError(
                "structure_ss_bridge_network: at least three residues with backbone atoms are required"
            )
        states = assign_states(angles, window=window)
        segments = [segment for segment in segment_rows(states, residues) if segment["state"] != "C"]
        if not segments:
            raise StepError(
                "structure_ss_bridge_network: no helical or strand segments were assigned"
            )
        for segment in segments:
            segment["length"] = segment["end"] - segment["start"] + 1
        ordered, ca = ca_coordinates(form, atom_dim, field_dim)
        residue_index = {label: index for index, label in enumerate(ordered)}
        rows = bridge_rows(segments, ca, residue_index, cutoff, contact)

        data = np.asarray([[row[1], row[2]] for row in rows], dtype=np.float32).reshape(len(rows), 2)
        out = Form(
            data=data,
            dims=[bridge_dim, "statistic"],
            labels={
                bridge_dim: {row[0]: position for position, row in enumerate(rows)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "n_segments": len(segments),
                "n_bridges": len(rows),
                "segments": [
                    {
                        "state": segment["state"],
                        "start": segment["start"],
                        "end": segment["end"],
                        "length": segment["length"],
                    }
                    for segment in segments
                ],
                "cutoff": cutoff,
                "contact": contact,
                "unit": "A",
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_segments": len(segments),
            "n_bridges": len(rows),
            "cutoff": cutoff,
            "contact": contact,
        }
        print(f"[structure_ss_bridge_network] {len(segments)} segments, {len(rows)} bridges")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
