"""Symmetry-aware RMSD between docked poses and a reference ligand pose."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, has_column
from src.task.step.steps.structure_ligand_pose_rmsd import symmetry_rmsd
from src.task.step.steps.vina_dock import parse_poses

_STATISTICS = ("rmsd", "max_deviation")
ELEMENT_SYMBOLS = {
    1: "H",
    6: "C",
    7: "N",
    8: "O",
    9: "F",
    15: "P",
    16: "S",
    17: "Cl",
    35: "Br",
    53: "I",
}


def pose_table(
    form: Form,
    pose_dim: str,
    atom_dim: str,
    field_dim: str,
    operator: str = "vina_pose_rmsd",
) -> tuple[list[str], np.ndarray, list[str]]:
    """Return pose labels, an ``(n_pose, n_atom, 3)`` coordinate array and elements."""

    if list(form.dims) != [pose_dim, atom_dim, field_dim]:
        raise StepError(
            f"{operator}: expected dims [{pose_dim}, {atom_dim}, {field_dim}], got {list(form.dims)}"
        )
    axes = [column_index(form, field_dim, name) for name in ("x", "y", "z")]
    for name in ("x", "y", "z"):
        if not has_column(form, field_dim, name):
            raise StepError(f"{operator}: the input has no '{name}' column")
    pose_labels = [
        label
        for label, _position in sorted(form.labels[pose_dim].items(), key=lambda item: item[1])
    ]
    atom_labels = [
        label
        for label, _position in sorted(form.labels[atom_dim].items(), key=lambda item: item[1])
    ]
    data = np.asarray(form.data, dtype=np.float64)
    coordinates = data[:, :, axes].reshape(len(pose_labels), len(atom_labels), 3)
    if has_column(form, field_dim, "atomic_number"):
        numbers = data[:, :, column_index(form, field_dim, "atomic_number")].reshape(
            len(pose_labels), len(atom_labels)
        )
        elements = [
            ELEMENT_SYMBOLS.get(int(round(value)), str(int(round(value))))
            for value in numbers[0]
        ]
    else:
        elements = ["C"] * len(atom_labels)
    return pose_labels, coordinates, elements


def reference_table(path: Path, operator: str = "vina_pose_rmsd") -> tuple[np.ndarray, list[str]]:
    """Read the reference PDBQT pose."""

    if not path.is_file():
        raise StepError(f"{operator}: reference_path {path} is not a file")
    if path.suffix.lower() != ".pdbqt":
        raise StepError(f"{operator}: reference_path must name a .pdbqt file")
    poses = parse_poses(path)
    if not poses:
        raise StepError(f"{operator}: the reference file holds no pose")
    pose = poses[0]
    return np.asarray(pose["coordinates"], dtype=np.float64), list(pose["elements"])


def rmsd_rows(
    coordinates: np.ndarray,
    elements: list[str],
    reference: np.ndarray,
    reference_elements: list[str],
    *,
    allow_symmetry: bool = True,
) -> list[dict]:
    """Superpose every pose onto the reference and return RMSD summaries."""

    if coordinates.shape[1] != reference.shape[0]:
        raise StepError(
            "vina_pose_rmsd: the pose and the reference must carry the same number of "
            f"atoms ({coordinates.shape[1]} vs {reference.shape[0]})"
        )
    if sorted(elements) != sorted(reference_elements) and allow_symmetry:
        raise StepError(
            "vina_pose_rmsd: the pose and the reference carry different element compositions"
        )
    rows: list[dict] = []
    for index in range(coordinates.shape[0]):
        rmsd, _order, deviations = symmetry_rmsd(
            coordinates[index],
            reference,
            elements,
            allow_symmetry=allow_symmetry,
        )
        rows.append(
            {
                "pose": index + 1,
                "rmsd": float(rmsd),
                "max_deviation": float(np.max(np.abs(deviations))) if len(deviations) else 0.0,
            }
        )
    return rows


class VinaPoseRmsdStep(Step):
    """Compare docked poses with a reference binding pose."""

    provider = "operon-core"
    parameters_file = "vina_pose_rmsd.VinaPoseRmsdStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vina_pose_rmsd",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pose RMSD to a reference",
        "description": (
            "Superpose every docked ligand pose onto a reference pose, matching "
            "symmetry-equivalent atoms, and report the RMSD and the largest "
            "per-atom deviation."
        ),
        "category": "Structure",
        "icon": "Ruler",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "pose_dim"},
                        {"param": "atom_dim"},
                        {"param": "field_dim"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 3,
                    "info": {"encoders": {"type": "object", "optional": True}},
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
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        pose_dim = str(params.get("pose_dim", "pose")) or "pose"
        atom_dim = str(params.get("atom_dim", "atom")) or "atom"
        field_dim = str(params.get("field_dim", "field")) or "field"
        out_name = str(params.get("output", "rmsd")) or "rmsd"
        reference_path = Path(str(params.get("reference_path", "")).strip()).expanduser()
        reference, reference_elements = reference_table(reference_path)
        pose_labels, coordinates, elements = pose_table(
            inputs[0], pose_dim, atom_dim, field_dim
        )
        if coordinates.shape[0] <= 1:
            raise StepError("vina_pose_rmsd: at least two poses are required")
        rows = rmsd_rows(
            coordinates,
            elements,
            reference,
            reference_elements,
            allow_symmetry=bool(params.get("allow_symmetry", True)),
        )
        best = min(rows, key=lambda row: row["rmsd"])
        labels = {
            pose_dim: {label: index for index, label in enumerate(pose_labels)},
            "statistic": {name: index for index, name in enumerate(_STATISTICS)},
        }
        data = np.zeros((len(rows), len(_STATISTICS)), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = (row["rmsd"], row["max_deviation"])
        ctx[out_name] = Form(
            data=data,
            dims=[pose_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "reference_path": str(reference_path),
                "n_poses": len(rows),
                "n_atoms": int(coordinates.shape[1]),
                "best_pose": best["pose"],
                "best_rmsd": best["rmsd"],
                "allow_symmetry": bool(params.get("allow_symmetry", True)),
            },
        )
        self._export_data = {
            "n_poses": len(rows),
            "best_pose": best["pose"],
            "best_rmsd": best["rmsd"],
            "rmsd": [row["rmsd"] for row in rows],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
