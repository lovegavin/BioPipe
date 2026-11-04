"""structure_md_ligand_rmsd: receptor-aligned ligand displacement."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_ligand_rmsd import (
    ligand_rmsd_series,
    load_frames,
    select_indices,
    superposition,
)


def _atom_line(serial, name, resname, chain, number, x, y, z):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"


def _system(tmp_path, shift=0.0):
    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(2, "CA", "GLY", "A", 2, 3.8, 0.0, 0.0),
        _atom_line(3, "CA", "SER", "A", 3, 7.6, 0.0, 0.0),
        _atom_line(4, "C1", "LIG", "L", 1, 5.0 + shift, 4.0, 0.0),
        _atom_line(5, "C2", "LIG", "L", 1, 6.0 + shift, 4.0, 0.0),
        _atom_line(6, "C3", "LIG", "L", 1, 5.5 + shift, 5.0, 0.0),
    ]
    topology = tmp_path / "topo.pdb"
    topology.write_text("\n".join(lines) + "\n")
    return topology


def test_superposition_identity():
    points = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    rotation, translation, rmsd = superposition(points, points)
    assert rmsd == pytest.approx(0.0)
    assert np.allclose(rotation, np.eye(3), atol=1e-9)
    assert np.allclose(translation, 0.0, atol=1e-9)


def test_ligand_shift_is_recovered(tmp_path):
    topology = _system(tmp_path, shift=0.0)
    lines = topology.read_text().splitlines()
    receptor, ligand = select_indices(lines, {"A"}, "LIG")
    coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    moved = coords.copy()
    moved[ligand, 0] += 1.0
    values = ligand_rmsd_series(np.stack([coords, moved]), receptor, ligand)
    assert values[0] == pytest.approx(0.0)
    assert values[1] == pytest.approx(1.0)


def test_global_rotation_is_removed(tmp_path):
    topology = _system(tmp_path, shift=0.0)
    lines = topology.read_text().splitlines()
    receptor, ligand = select_indices(lines, {"A"}, "LIG")
    coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    angle = np.radians(30.0)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    rotated = coords @ rotation.T + np.array([10.0, -4.0, 2.0])
    values = ligand_rmsd_series(np.stack([coords, rotated]), receptor, ligand)
    assert values[1] == pytest.approx(0.0, abs=1e-9)


def test_run_round_trip(tmp_path):
    topology = _system(tmp_path, shift=0.0)
    lines = topology.read_text().splitlines()
    coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    npy = tmp_path / "frames.npy"
    moved = coords.copy()
    moved[3:, 2] += 2.0
    np.save(npy, np.stack([coords, moved]) / 10.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_ligand_rmsd", "params": {"output": "ligand_rmsd", "trajectory_path": str(npy), "topology_path": str(topology), "receptor_chains": "A", "ligand_resname": "LIG"}}])
    table = ctx["ligand_rmsd"]
    assert table.data.shape == (2, 1)
    assert table.info["n_ligand_atoms"] == 3
    assert table.info["final_rmsd"] == pytest.approx(2.0)


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    topology = _system(tmp_path)
    lines = topology.read_text().splitlines()
    with pytest.raises(StepError, match="no 'XXX' atoms"):
        select_indices(lines, {"A"}, "XXX")
