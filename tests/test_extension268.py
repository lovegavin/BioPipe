from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context import Context
from src.task.runner import run


def _ctx(task_dir: Path, out_name: str, params: dict) -> Context:
    ctx = Context(str(task_dir / "task"), {"params": {}})
    ctx.step_params = {"output": out_name, **params}
    return ctx

from src.task.step.steps.vina_pose_rmsd import pose_table, reference_table, rmsd_rows

FIELDS = ("x", "y", "z", "charge", "atomic_number")
COORDS = np.asarray(
    [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [0.0, 1.5, 0.0], [0.0, 0.0, 1.5]]
)
NUMBERS = [6, 6, 8, 7]
ELEMENTS = ["C", "C", "O", "N"]


def _pose_form(poses: np.ndarray, numbers=NUMBERS) -> Form:
    n_pose, n_atom = poses.shape[0], poses.shape[1]
    data = np.zeros((n_pose, n_atom, len(FIELDS)), dtype=np.float32)
    for pose_index in range(n_pose):
        for atom_index in range(n_atom):
            data[pose_index, atom_index] = (
                poses[pose_index, atom_index, 0],
                poses[pose_index, atom_index, 1],
                poses[pose_index, atom_index, 2],
                0.0,
                float(numbers[atom_index]),
            )
    return Form(
        data=data,
        dims=["pose", "atom", "field"],
        labels={
            "pose": {f"pose{i + 1}": i for i in range(n_pose)},
            "atom": {f"atom{i + 1}": i for i in range(n_atom)},
            "field": {name: i for i, name in enumerate(FIELDS)},
        },
        info={"missing_code": np.nan},
    )


def _pdbqt(path: Path, coords: np.ndarray, numbers=NUMBERS) -> Path:
    types = {6: "C", 8: "OA", 7: "N", 1: "H"}
    rows = []
    for index, (xyz, number) in enumerate(zip(coords, numbers), start=1):
        rows.append(
            "ATOM  {serial:5d}  C   LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}"
            "  1.00  0.00    +0.000 {atype:<2s}".format(
                serial=index,
                x=xyz[0],
                y=xyz[1],
                z=xyz[2],
                atype=types.get(number, "C"),
            )
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_reference_table_reads_first_model(tmp_path):
    path = _pdbqt(tmp_path / "ref.pdbqt", COORDS)
    coordinates, elements = reference_table(path)
    assert coordinates.shape == (4, 3)
    assert elements == ELEMENTS


def test_pose_table_maps_atomic_numbers(tmp_path):
    form = _pose_form(np.stack([COORDS, COORDS]))
    labels, coordinates, elements = pose_table(form, "pose", "atom", "field")
    assert labels == ["pose1", "pose2"]
    assert coordinates.shape == (2, 4, 3)
    assert elements == ELEMENTS


def test_rmsd_is_zero_for_translation_and_rotation():
    rotated = COORDS @ np.asarray([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    translated = rotated + np.asarray([5.0, -2.0, 3.0])
    rows = rmsd_rows(np.stack([COORDS, translated]), ELEMENTS, COORDS, ELEMENTS)
    assert rows[0]["rmsd"] == pytest.approx(0.0, abs=1e-6)
    assert rows[1]["rmsd"] == pytest.approx(0.0, abs=1e-6)


def test_rmsd_grows_for_a_strained_pose():
    strained = COORDS.copy()
    strained[1] += (1.0, 0.0, 0.0)
    rows = rmsd_rows(np.stack([strained]), ELEMENTS, COORDS, ELEMENTS)
    assert rows[0]["rmsd"] > 0.2


def test_element_composition_is_checked():
    with pytest.raises(StepError, match="different element compositions"):
        rmsd_rows(np.stack([COORDS]), ["C", "C", "O", "O"], COORDS, ELEMENTS)


def test_pose_table_validates_dimensions():
    bad = Form(
        data=np.zeros((2, 4)),
        dims=["pose", "atom"],
        labels={"pose": {"a": 0, "b": 1}, "atom": {str(i): i for i in range(4)}},
        info={},
    )
    with pytest.raises(StepError, match="expected dims"):
        pose_table(bad, "pose", "atom", "field")


def test_run_and_errors(tmp_path):
    reference = _pdbqt(tmp_path / "ref.pdbqt", COORDS)
    poses = np.stack([COORDS, COORDS + 2.0])
    form = _pose_form(poses)
    params = {"reference_path": str(reference)}
    ctx = _ctx(tmp_path, "rmsd", params)
    ctx["poses"] = form
    run(ctx, [{"name": "vina_pose_rmsd", "inputs": ["poses"], "params": params}])
    result = ctx["rmsd"]
    assert result.data.shape == (2, 2)
    assert result.info["n_poses"] == 2
    assert result.info["best_pose"] == 1

    bad = dict(params)
    bad["reference_path"] = str(tmp_path / "missing.pdbqt")
    ctx = _ctx(tmp_path, "rmsd", bad)
    ctx["poses"] = form
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "vina_pose_rmsd", "inputs": ["poses"], "params": bad}])

    bad = dict(params)
    bad["reference_path"] = str(tmp_path / "ref.pdb")
    Path(bad["reference_path"]).write_text("x")
    ctx = _ctx(tmp_path, "rmsd", bad)
    ctx["poses"] = form
    with pytest.raises(StepError, match="must name a .pdbqt file"):
        run(ctx, [{"name": "vina_pose_rmsd", "inputs": ["poses"], "params": bad}])
