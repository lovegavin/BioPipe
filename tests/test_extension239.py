"""Tests for the ligand pose RMSD operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_pose_rmsd import (
    kabsch,
    ligand_atoms,
    symmetry_rmsd,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    position = {name: index for index, name in enumerate(COLUMNS)}
    arrays: list[np.ndarray] = []
    encoders = {}
    for name in COLUMNS:
        column = [row[position[name]] for row in rows]
        if name in ("x", "y", "z", "residue_number"):
            arrays.append(np.asarray(column, dtype=np.float64))
        else:
            encoder = LabelEncoder()
            arrays.append(np.asarray(encoder.fit_transform(column), dtype=np.float64))
            encoders[name] = encoder
    return Form(
        data=np.column_stack(arrays).astype(np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


LIGAND = [
    (0.0, 0.0, 0.0, 1, "LIG", "A", "N1", "N"),
    (1.5, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
    (0.0, 1.5, 0.0, 1, "LIG", "A", "C2", "C"),
    (0.0, 0.0, 1.5, 1, "LIG", "A", "O1", "O"),
]

PROTEIN = [
    (5.0, 5.0, 5.0, 20, "ALA", "B", "CA", "C"),
    (6.0, 5.0, 5.0, 21, "ALA", "B", "CA", "C"),
]


def _run(tmp_path: Path, pose_rows, reference_rows, **params) -> Context:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pose"] = _pdb_form(pose_rows)
    ctx["reference"] = _pdb_form(reference_rows)
    run(
        ctx,
        [
            {
                "name": "structure_ligand_pose_rmsd",
                "inputs": ["pose", "reference"],
                "params": {"output": "rmsd", **params},
            }
        ],
    )
    return ctx


def test_kabsch_recovers_a_rigid_transform() -> None:
    reference = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 1.5, 0.0], [0.0, 0.0, 1.5]]
    )
    angle = 0.7
    rotation = np.asarray(
        [
            [np.cos(angle), -np.sin(angle), 0.0],
            [np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    pose = reference @ rotation.T + np.asarray([4.0, -2.0, 1.0])
    rmsd, _rotation = kabsch(pose, reference)
    assert rmsd < 1e-9


def test_symmetry_aware_matching_of_equivalent_atoms() -> None:
    reference = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 1.5, 0.0], [0.0, 0.0, 1.5]]
    )
    pose = reference.copy()
    pose[[1, 2]] = pose[[2, 1]]
    elements = ["N", "C", "C", "O"]
    strict, _order, _deviations = symmetry_rmsd(pose, reference, elements, allow_symmetry=False)
    relaxed, order, deviations = symmetry_rmsd(pose, reference, elements, allow_symmetry=True)
    assert strict > 0.1
    assert relaxed < 1e-9
    assert order.tolist() == [0, 2, 1, 3]
    assert deviations.max() < 1e-9


def test_ligand_atoms_extracts_only_the_requested_residue() -> None:
    form = _pdb_form(LIGAND + PROTEIN)
    coordinates, elements, labels, counts = ligand_atoms(
        form, "atom", "field", {"LIG"}, "structure_ligand_pose_rmsd"
    )
    assert coordinates.shape == (4, 3)
    assert elements == ["N", "C", "C", "O"]
    assert labels[0] == "A:LIG1:N1"
    assert counts == {"C": 2, "N": 1, "O": 1}


def test_runner_identity_after_translation(tmp_path: Path) -> None:
    translated = [(x + 5.0, y - 3.0, z + 2.0, *rest) for x, y, z, *rest in LIGAND]
    ctx = _run(tmp_path, translated, LIGAND)
    form = ctx["rmsd"]
    assert form.dims == ["pose_atom", "statistic"]
    assert form.data.shape == (4, 1)
    assert form.info["rmsd"] == pytest.approx(0.0, abs=1e-6)
    assert form.info["permutation"] == [0, 1, 2, 3]
    assert form.info["n_atoms"] == 4


def test_runner_element_mismatch(tmp_path: Path) -> None:
    broken = LIGAND[:3] + [(0.0, 0.0, 1.5, 1, "LIG", "A", "S1", "S")]
    with pytest.raises(StepError, match="different element compositions"):
        _run(tmp_path, broken, LIGAND)


def test_validation_errors(tmp_path: Path) -> None:
    with pytest.raises(StepError, match="no ligand atom matches"):
        _run(tmp_path, PROTEIN, LIGAND, pose_resnames="XYZ")
    ctx = _run(tmp_path, LIGAND[:2], LIGAND[:2], allow_symmetry=False)
    assert ctx["rmsd"].data.shape == (2, 1)
    with pytest.raises(ValueError, match="symmetry_rmsd|shape"):
        symmetry_rmsd(np.zeros((3, 3)), np.zeros((4, 3)), ["C", "C", "O", "N"])
