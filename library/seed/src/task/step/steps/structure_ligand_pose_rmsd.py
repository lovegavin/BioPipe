"""Symmetry-aware RMSD between two ligand poses.

The pose is superposed onto the reference with the Kabsch algorithm; when
``allow_symmetry`` is on, atoms with the same element are re-matched with the
Hungarian assignment inside each element group and the superposition is repeated
until the matching stops changing.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, decode_column, has_column

_STATISTICS = ("deviation",)


def kabsch(pose: np.ndarray, reference: np.ndarray) -> tuple[float, np.ndarray]:
    """Optimal rotation of ``pose`` onto ``reference`` and the resulting RMSD."""

    pose_centred = pose - pose.mean(axis=0)
    reference_centred = reference - reference.mean(axis=0)
    covariance = pose_centred.T @ reference_centred
    left, _values, right = np.linalg.svd(covariance)
    sign = np.sign(np.linalg.det(right.T @ left.T))
    rotation = right.T @ np.diag([1.0, 1.0, sign]) @ left.T
    diff = pose_centred @ rotation.T - reference_centred
    rmsd = float(np.sqrt(np.mean(np.sum(diff**2, axis=1))))
    return rmsd, rotation


def transformed(pose: np.ndarray, reference: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    """Pose coordinates after centring, rotating and re-centring on the reference."""

    pose_centred = pose - pose.mean(axis=0)
    return pose_centred @ rotation.T + reference.mean(axis=0)


def symmetry_rmsd(
    pose: np.ndarray,
    reference: np.ndarray,
    elements,
    *,
    allow_symmetry: bool = True,
    iterations: int = 20,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Superpose two equal-length atom sets, matching equivalent atoms when asked."""
    pose = np.asarray(pose, dtype=np.float64)
    reference = np.asarray(reference, dtype=np.float64)
    if pose.shape != reference.shape:
        raise ValueError("symmetry_rmsd: the two atom sets must have the same shape")
    from itertools import permutations, product
    from math import factorial

    elements_array = np.asarray(elements, dtype=object)
    best_rmsd, _best_rotation = kabsch(pose, reference)
    best_order = np.arange(len(pose), dtype=int)

    if allow_symmetry:
        groups = [
            np.flatnonzero(elements_array == element)
            for element in sorted(set(elements))
        ]
        groups = [group for group in groups if len(group) > 1]
        combinations = 1
        for group in groups:
            combinations *= factorial(int(len(group)))
        if combinations <= 5040:
            for choices in product(*[list(permutations(group.tolist())) for group in groups]):
                mapping = np.arange(len(pose))
                for group, choice in zip(groups, choices):
                    for source_index, target_index in zip(group.tolist(), choice):
                        mapping[source_index] = target_index
                rmsd, _rotation = kabsch(pose, reference[mapping])
                if rmsd < best_rmsd - 1e-12:
                    best_rmsd = rmsd
                    best_order = mapping
        else:
            order = np.arange(len(pose))
            seen: set[tuple[int, ...]] = set()
            for _ in range(max(1, iterations)):
                rmsd, rotation = kabsch(pose, reference[order])
                if rmsd < best_rmsd:
                    best_rmsd = rmsd
                    best_order = order.copy()
                rotated = transformed(pose, reference[order], rotation)
                updated = order.copy()
                for element in sorted(set(elements)):
                    rows = np.flatnonzero(elements_array == element)
                    if len(rows) < 2:
                        continue
                    cost = np.sum(
                        (rotated[rows][:, None, :] - reference[rows][None, :, :]) ** 2,
                        axis=2,
                    )
                    linear_sum_assignment = __import__(
                        "scipy.optimize", fromlist=["linear_sum_assignment"]
                    ).linear_sum_assignment

                    row_index, column_index = linear_sum_assignment(cost)
                    updated[rows[row_index]] = rows[column_index]
                key = tuple(int(value) for value in updated)
                if key in seen or np.array_equal(updated, order):
                    break
                seen.add(key)
                order = updated
            rmsd, _rotation = kabsch(pose, reference[order])
            if rmsd < best_rmsd:
                best_rmsd = rmsd
                best_order = order.copy()

    rmsd, rotation = kabsch(pose, reference[best_order])
    rotated = transformed(pose, reference[best_order], rotation)
    deviations = np.linalg.norm(rotated - reference[best_order], axis=1)
    return rmsd, best_order, deviations


def ligand_atoms(
    form, atom_dim: str, field_dim: str, resnames: set[str], operator: str
) -> tuple[np.ndarray, list[str], list[str]]:
    """Coordinates, elements and labels of the ligand atoms in a PDB atom form."""

    for column in ("x", "y", "z", "resname", "element"):
        if not has_column(form, field_dim, column):
            raise StepError(f"{operator}: the structure form has no '{column}' column")
    resname_column = np.asarray(decode_column(form, field_dim, "resname"), dtype=object)
    mask = np.asarray([str(name).strip().upper() in resnames for name in resname_column])
    if not mask.any():
        listed = ", ".join(sorted(resnames)) or "(none)"
        raise StepError(
            f"{operator}: no ligand atom matches the requested residue names ({listed})"
        )
    coordinates = np.column_stack(
        [
            np.asarray(form.data[mask, column_index(form, field_dim, axis)], dtype=np.float64)
            for axis in ("x", "y", "z")
        ]
    )
    elements = [str(value).strip().upper() for value in np.asarray(decode_column(form, field_dim, "element"), dtype=object)[mask]]
    labels: list[str] = []
    if has_column(form, field_dim, "atom_name"):
        names = np.asarray(decode_column(form, field_dim, "atom_name"), dtype=object)[mask]
    else:
        names = np.asarray(["X"] * int(mask.sum()), dtype=object)
    chains = (
        np.asarray(decode_column(form, field_dim, "chain"), dtype=object)[mask]
        if has_column(form, field_dim, "chain")
        else np.asarray([""] * int(mask.sum()), dtype=object)
    )
    numbers = (
        np.asarray(decode_column(form, field_dim, "residue_number"), dtype=object)[mask]
        if has_column(form, field_dim, "residue_number")
        else np.asarray([""] * int(mask.sum()), dtype=object)
    )
    for index in range(int(mask.sum())):
        labels.append(f"{chains[index]}:{resname_column[mask][index]}{numbers[index]}:{names[index]}")
    counts = {element: elements.count(element) for element in sorted(set(elements))}
    return coordinates, elements, labels, counts


class StructureLigandPoseRmsdStep(Step):
    """Symmetry-corrected ligand pose RMSD with per-atom deviations."""

    provider = "operon-core"

    parameters_file = "structure_ligand_pose_rmsd.StructureLigandPoseRmsdStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_pose_rmsd",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand pose RMSD",
        "description": (
            "Superpose a ligand pose onto a reference pose with the Kabsch algorithm and, when "
            "requested, re-match same-element atoms with the Hungarian assignment to obtain a "
            "symmetry-corrected RMSD. Emits per-atom deviations and the matched permutation."
        ),
        "category": "Structure",
        "icon": "CirclesThree",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        pose_form, reference_form = inputs
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        pose_dim = str(params.get("pose_dim") or "pose_atom")
        allow_symmetry = bool(
            params.get("allow_symmetry") if params.get("allow_symmetry") is not None else True
        )
        iterations = int(params.get("max_iterations") if params.get("max_iterations") is not None else 20)
        out_name = str(params.get("output") or "rmsd")
        pose_names = _resname_set(params.get("pose_resnames"), "LIG")
        reference_names = _resname_set(params.get("reference_resnames"), None) or pose_names

        if iterations < 1:
            raise StepError("structure_ligand_pose_rmsd: max_iterations must be at least 1")

        pose, pose_elements, pose_labels, pose_counts = ligand_atoms(
            pose_form, atom_dim, field_dim, pose_names, "structure_ligand_pose_rmsd"
        )
        reference, reference_elements, _reference_labels, reference_counts = ligand_atoms(
            reference_form, atom_dim, field_dim, reference_names, "structure_ligand_pose_rmsd"
        )
        if pose_counts != reference_counts:
            raise StepError(
                "structure_ligand_pose_rmsd: the pose and the reference carry different element "
                f"compositions ({pose_counts} vs {reference_counts})"
            )
        rmsd, order, deviations = symmetry_rmsd(
            pose, reference, pose_elements, allow_symmetry=allow_symmetry, iterations=iterations
        )
        data = np.asarray(deviations, dtype=np.float32).reshape(len(deviations), 1)
        out = Form(
            data=data,
            dims=[pose_dim, "statistic"],
            labels={
                pose_dim: {label: index for index, label in enumerate(pose_labels)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "rmsd": rmsd,
                "n_atoms": len(pose),
                "allow_symmetry": allow_symmetry,
                "permutation": [int(index) for index in order],
                "elements": pose_elements,
                "max_deviation": float(deviations.max()),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "rmsd": rmsd,
            "n_atoms": len(pose),
            "allow_symmetry": allow_symmetry,
            "max_deviation": float(deviations.max()),
        }
        print(f"[structure_ligand_pose_rmsd] rmsd {rmsd:.4f} A over {len(pose)} atoms")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


def _resname_set(value, default: str | None) -> set[str]:
    text = str(value or "").strip()
    if not text:
        return set() if default is None else {default}
    return {token.strip().upper() for token in text.replace(",", " ").split() if token.strip()}
