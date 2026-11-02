"""structure_md_salt_bridge_occupancy: charged-pair persistence."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_salt_bridge_occupancy import (
    charge_groups,
    load_frames,
    salt_bridge_rows,
)


def _atom_line(serial, name, resname, chain, number, x, y, z):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           N"


def _synthetic(tmp_path):
    lines = [
        _atom_line(1, "OD1", "ASP", "A", 10, 0.0, 0.0, 0.0),
        _atom_line(3, "NZ", "LYS", "B", 20, 3.0, 0.0, 0.0),
        _atom_line(4, "NZ", "LYS", "B", 21, 12.0, 0.0, 0.0),
    ]
    topology = tmp_path / "topo.pdb"
    topology.write_text("\n".join(lines) + "\n")
    frames = np.zeros((3, 3, 3))
    frames[0] = [[0, 0, 0], [3, 0, 0], [12, 0, 0]]
    frames[1] = [[0, 0, 0], [5.0, 0, 0], [12, 0, 0]]
    frames[2] = [[0, 0, 0], [2.0, 0, 0], [12, 0, 0]]
    npy = tmp_path / "frames.npy"
    np.save(npy, frames / 10.0)
    return topology, npy


def test_charge_groups():
    acids, bases, atom_sets = charge_groups([
        _atom_line(1, "OD1", "ASP", "A", 10, 0.0, 0.0, 0.0),
        _atom_line(2, "NZ", "LYS", "B", 20, 3.0, 0.0, 0.0),
    ])
    assert acids == [("A", "ASP", 10)]
    assert bases == [("B", "LYS", 20)]


def test_rows_hand_case():
    distances = np.asarray([[[2.9, 9.0]], [[4.5, 9.0]], [[3.5, 9.0]]])
    acids = [("A", "ASP", 10)]
    bases = [("B", "LYS", 20), ("B", "LYS", 21)]
    rows = salt_bridge_rows(distances, acids, bases, 4.0, 0.5)
    assert len(rows) == 1
    assert rows[0]["occupancy"] == pytest.approx(2 / 3)


def test_run_occupancy(tmp_path):
    topology, trajectory = _synthetic(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_salt_bridge_occupancy", "params": {"output": "salt_bridges", "trajectory_path": str(trajectory), "topology_path": str(topology), "cutoff": 4.0, "min_occupancy": 0.5}}])
    table = ctx["salt_bridges"]
    assert table.data.shape[0] == 1
    labels = table.labels["salt_bridge"]
    assert "A:10:ASP-B:20:LYS" in labels
    assert table.data[0][0] == pytest.approx(2 / 3, rel=1e-5)
    assert table.data[0][2] == pytest.approx(2.0, abs=1e-3)


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="at least two frames"):
        topology, trajectory = _synthetic(tmp_path)
        single = tmp_path / "single.npy"
        np.save(single, np.load(trajectory)[:1])
        run(ctx, [{"name": "structure_md_salt_bridge_occupancy", "params": {"output": "salt_bridges", "trajectory_path": str(single), "topology_path": str(topology)}}])
