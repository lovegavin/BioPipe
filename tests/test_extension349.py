"""structure_md_interface_occupancy: contact counting and runner contract."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_interface_occupancy import (
    load_frames,
    occupancy_rows,
    select_chains,
)


def _system(frames=3):
    coords = np.zeros((frames, 4, 3), dtype=np.float64)
    labels = np.array(["A:ALA:1", "A:GLY:2", "B:SER:1", "B:THR:2"])
    chain = np.array(["A", "A", "B", "B"])
    heavy = np.array([True, True, True, True], dtype=bool)
    # A:1 near B:1 at 3 A; A:2 starts 20 A away and approaches in later frames
    for index in range(frames):
        coords[index] = [
            [0.0, 0.0, 0.0],
            [20.0 - 9.0 * index, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [3.0, 0.0, 8.0],
        ]
    return coords, labels, chain, heavy


def test_load_frames_validation(tmp_path):
    path = tmp_path / "t.npy"
    np.save(path, np.zeros((3, 4, 3)))
    assert load_frames(path).shape == (3, 4, 3)
    np.save(path, np.zeros((4, 3)))
    with pytest.raises(StepError, match="expected"):
        load_frames(path)
    np.save(path, np.zeros((1, 4, 3)))
    with pytest.raises(StepError, match="at least two frames"):
        load_frames(path)


def test_occupancy_rows_hand_case():
    coords, labels, chain, heavy = _system(3)
    rows = occupancy_rows(coords, labels, chain, heavy, binder_chains={"A"}, target_chains={"B"}, cutoff=5.0)
    table = {row["label"]: row for row in rows}
    assert table["A:ALA:1"]["n_frames"] == 3
    assert table["A:GLY:2"]["n_frames"] == 1
    assert table["A:ALA:1"]["occupancy"] == pytest.approx(1.0)
    assert "B:THR:2" not in table  # never in contact, filtered out


def test_select_chains_defaults_and_errors():
    chain = np.array(["A", "A", "B", "B"])
    assert select_chains({}, chain) == ({"A"}, {"B"})
    assert select_chains({"binder_chains": "B"}, chain) == ({"B"}, {"A"})
    with pytest.raises(StepError, match="absent"):
        select_chains({"binder_chains": "Z"}, chain)


def test_run_round_trip(tmp_path):
    coords, _, _, _ = _system(3)
    np.save(tmp_path / "traj.npy", coords)
    (tmp_path / "top.pdb").write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 90.00           C\n"
        "ATOM      2  CA  GLY A   2      20.000   0.000   0.000  1.00 90.00           C\n"
        "ATOM      3  CA  SER B   1       3.000   0.000   0.000  1.00 90.00           C\n"
        "ATOM      4  CA  THR B   2       3.000   0.000   8.000  1.00 90.00           C\n"
    )
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_interface_occupancy", "params": {"output": "interface", "trajectory_path": str(tmp_path / "traj.npy"), "topology_path": str(tmp_path / "top.pdb"), "cutoff": 5.0}}])
    result = ctx["interface"]
    assert result.dims == ["residue", "statistic"]
    assert result.info["n_frames"] == 3
    assert result.info["n_interface_residues"] >= 2
