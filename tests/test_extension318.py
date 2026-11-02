"""structure_md_contact_occupancy: contact frequencies over a trajectory."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_contact_occupancy import (
    contact_table,
    load_frames,
    residue_groups,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TOPOLOGY = FIXTURES / "vhh_1mel.pdb"


def _atom_line(serial, name, resname, chain, number, x, y, z):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {name[0]}"


def _synthetic(tmp_path):
    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(2, "CA", "GLY", "B", 2, 3.0, 0.0, 0.0),
        _atom_line(3, "CA", "SER", "B", 3, 20.0, 0.0, 0.0),
    ]
    path = tmp_path / "topo.pdb"
    path.write_text("\n".join(lines) + "\n")
    frames = np.zeros((3, 3, 3))
    frames[0] = [[0, 0, 0], [3, 0, 0], [20, 0, 0]]
    frames[1] = [[0, 0, 0], [8, 0, 0], [20, 0, 0]]
    frames[2] = [[0, 0, 0], [4, 0, 0], [20, 0, 0]]
    npy = tmp_path / "frames.npy"
    np.save(npy, frames / 10.0)
    return path, npy


def test_residue_groups_and_table():
    groups, order = residue_groups([
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(2, "CA", "GLY", "B", 2, 3.0, 0.0, 0.0),
    ])
    assert order == [("A", "ALA", 1), ("B", "GLY", 2)]
    assert len(groups[("A", "ALA", 1)]) == 1
    distances = np.asarray([[4.0, 18.0, 30.0], [6.0, 18.0, 30.0], [2.0, 18.0, 30.0]])
    keys = [("A", "ALA", 1), ("B", "GLY", 2), ("B", "SER", 3)]
    rows = contact_table(distances, keys, 5.0, 0.5)
    assert rows[0]["occupancy"] == pytest.approx(2 / 3)
    assert rows[0]["min_distance"] == pytest.approx(2.0)


def test_run_occupancy_hand_case(tmp_path):
    topology, trajectory = _synthetic(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_contact_occupancy", "params": {"output": "contacts", "trajectory_path": str(trajectory), "topology_path": str(topology), "cutoff": 5.0, "min_occupancy": 0.5}}])
    table = ctx["contacts"]
    assert table.data.shape == (1, 3)
    assert table.info["n_frames"] == 3
    assert "A:1-B:2" in table.labels["contact"]
    assert table.data[0][0] == pytest.approx(2 / 3, rel=1e-5)


def test_distances_match_brute_force(tmp_path):
    """Compare the KD-tree distances with a direct distance matrix."""

    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(2, "CB", "ALA", "A", 1, 1.0, 0.0, 0.0),
        _atom_line(3, "CA", "GLY", "B", 2, 4.0, 0.0, 0.0),
        _atom_line(4, "CA", "SER", "B", 3, 30.0, 0.0, 0.0),
    ]
    topology = tmp_path / "topo.pdb"
    topology.write_text("\n".join(lines) + "\n")
    frames = np.zeros((2, 4, 3))
    frames[0] = [[0, 0, 0], [1, 0, 0], [4, 0, 0], [30, 0, 0]]
    frames[1] = [[0, 0, 0], [1, 0, 0], [4.5, 0, 0], [30, 0, 0]]
    npy = tmp_path / "frames.npy"
    np.save(npy, frames / 10.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_contact_occupancy", "params": {"output": "contacts", "trajectory_path": str(npy), "topology_path": str(topology), "cutoff": 4.0, "min_occupancy": 0.0}}])
    table = ctx["contacts"]
    labels = table.labels["contact"]
    assert "A:1-B:2" in labels
    row = table.data[labels["A:1-B:2"]]
    # brute force minimum heavy-atom distance: atom 2 to atom 3 = 3.0 and 3.5 A
    assert row[2] == pytest.approx(3.0, abs=1e-3)
    assert row[1] == pytest.approx(3.25, abs=1e-3)
    assert row[0] == pytest.approx(1.0, abs=1e-5)


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="at least two frames"):
        topology, trajectory = _synthetic(tmp_path)
        single = tmp_path / "single.npy"
        np.save(single, np.load(trajectory)[:1])
        run(ctx, [{"name": "structure_md_contact_occupancy", "params": {"output": "contacts", "trajectory_path": str(single), "topology_path": str(topology)}}])
