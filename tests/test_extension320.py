"""structure_md_hbond_occupancy: geometric hydrogen-bond persistence."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_hbond_occupancy import (
    hbond_geometry,
    load_frames,
    parse_atoms,
    donor_hydrogens,
)


def _atom_line(serial, name, resname, chain, number, x, y, z, element="N"):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element}"


def _synthetic(tmp_path):
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
        _atom_line(2, "H", "ALA", "A", 1, 1.0, 0.0, 0.0, "H"),
        _atom_line(3, "OD1", "ASP", "B", 2, 3.75, 0.0, 0.0, "O"),
    ]
    topology = tmp_path / "topo.pdb"
    topology.write_text("\n".join(lines) + "\n")
    # frame 0: H...O 2.75 A, angle D-H-A 180 deg (bonded)
    # frame 1: H...O 3.9 A (not bonded)
    # frame 2: H...O 2.75 A but angle 90 deg (not bonded)
    frames = np.zeros((3, 3, 3))
    frames[0] = [[0, 0, 0], [1.0, 0, 0], [3.75, 0, 0]]
    frames[1] = [[0, 0, 0], [1.0, 0, 0], [4.9, 0, 0]]
    frames[2] = [[0, 0, 0], [1.0, 0, 0], [1.0, 2.75, 0]]
    npy = tmp_path / "frames.npy"
    np.save(npy, frames / 10.0)
    return topology, npy


def test_geometry_angles():
    coordinates = np.asarray([[0, 0, 0], [1, 0, 0], [1.0, 2.75, 0]], dtype=float)
    distance, angle = hbond_geometry(coordinates, 0, 1, 2)
    assert distance == pytest.approx(2.75)
    assert angle == pytest.approx(90.0)
    straight = np.asarray([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    distance, angle = hbond_geometry(straight, 0, 1, 2)
    assert angle == pytest.approx(180.0)


def test_donor_detection():
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
        _atom_line(2, "H", "ALA", "A", 1, 1.0, 0.0, 0.0, "H"),
    ]
    atoms = parse_atoms(lines)
    donors = donor_hydrogens(atoms, np.asarray([[0, 0, 0], [1, 0, 0]], dtype=float))
    assert donors == [(0, 1)]


def test_run_occupancy_hand_case(tmp_path):
    topology, npy = _synthetic(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_hbond_occupancy", "params": {"output": "hbonds", "trajectory_path": str(npy), "topology_path": str(topology), "cutoff": 3.5, "angle_cutoff": 120.0, "min_occupancy": 0.1}}])
    table = ctx["hbonds"]
    assert table.data.shape == (1, 3)
    assert table.data[0][0] == pytest.approx(1 / 3, rel=1e-5)
    assert "A:1:N-B:2:OD1" in table.labels["hbond"]
    assert table.info["n_candidates"] == 1


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="carries no hydrogen"):
        topology, npy = _synthetic(tmp_path)
        no_h = tmp_path / "no_h.pdb"
        no_h.write_text("\n".join([
            _atom_line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
            _atom_line(2, "CA", "ALA", "A", 1, 1.0, 0.0, 0.0, "C"),
        ]) + "\n")
        two_atom = tmp_path / "two.npy"
        np.save(two_atom, np.load(npy)[:, :2])
        run(ctx, [{"name": "structure_md_hbond_occupancy", "params": {"output": "hbonds", "trajectory_path": str(two_atom), "topology_path": str(no_h)}}])
