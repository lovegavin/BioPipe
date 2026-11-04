"""structure_md_dihedral_occupancy: phi/psi and Ramachandran occupancy."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_dihedral_occupancy import (
    backbone_atoms,
    frame_angles,
    load_frames,
    occupancy_table,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TOPOLOGY = FIXTURES / "vhh_1mel.pdb"


def _atom_line(serial, name, resname, chain, number, x, y, z):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"


def test_backbone_collection_and_angles():
    lines = [
        _atom_line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom_line(2, "CA", "ALA", "A", 1, 1.0, 0.2, 0.0),
        _atom_line(3, "C", "ALA", "A", 1, 2.0, 1.0, 0.0),
        _atom_line(4, "N", "GLY", "A", 2, 3.0, 1.0, 0.3),
        _atom_line(5, "CA", "GLY", "A", 2, 4.0, 1.2, 0.2),
        _atom_line(6, "C", "GLY", "A", 2, 5.0, 2.0, 0.0),
        _atom_line(7, "N", "SER", "A", 3, 6.0, 2.0, 0.4),
        _atom_line(8, "CA", "SER", "A", 3, 7.0, 2.1, 0.1),
        _atom_line(9, "C", "SER", "A", 3, 8.0, 3.0, 0.2),
    ]
    residues = backbone_atoms(lines)
    assert len(residues) == 3
    coordinates = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    phi, psi = frame_angles(coordinates, residues)
    assert np.isnan(phi[0]) and np.isnan(psi[-1])
    assert all(np.isfinite(phi[1:]))
    assert all(np.isfinite(psi[:-1]))


def test_occupancy_table_hand_case():
    phi = np.array([[-60.0], [-60.0], [-120.0]])
    psi = np.array([[-40.0], [-45.0], [130.0]])
    rows = occupancy_table(phi, psi, ["A:ALA:1"])
    assert rows[0]["alpha_occupancy"] == pytest.approx(2 / 3)
    assert rows[0]["beta_occupancy"] == pytest.approx(1 / 3)
    assert rows[0]["dominant"] == 0
    assert rows[0]["phi_mean"] == pytest.approx(-80.0)


def test_run_round_trip(tmp_path):
    lines = [line for line in TOPOLOGY.read_text().splitlines() if line.startswith(("ATOM", "HETATM"))]
    coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    npy = tmp_path / "frames.npy"
    np.save(npy, np.stack([coords, coords + 0.2]) / 10.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_dihedral_occupancy", "params": {"output": "dihedrals", "trajectory_path": str(npy), "topology_path": str(TOPOLOGY), "chains": "A"}}])
    table = ctx["dihedrals"]
    assert table.data.shape[1] == 5
    assert table.info["n_frames"] == 2
    assert table.info["regions"] == ["alpha", "beta", "left_alpha", "other"]


def test_matches_mdtraj_angles(tmp_path):
    mdtraj = pytest.importorskip("mdtraj")
    lines = [line for line in TOPOLOGY.read_text().splitlines() if line.startswith(("ATOM", "HETATM"))]
    coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    reference = mdtraj.load(str(TOPOLOGY))
    traj = mdtraj.Trajectory(xyz=(np.stack([coords, coords]) * 0.1).astype(np.float32), topology=reference.topology)
    phi_idx, phi = mdtraj.compute_phi(traj)
    psi_idx, psi = mdtraj.compute_psi(traj)
    residues = backbone_atoms(lines)
    ours_phi, _ = frame_angles(coords, residues)
    positions = {residue["N"]: index for index, residue in enumerate(residues)}
    first = phi_idx[0]
    position = positions[first[1]]
    assert np.degrees(phi[0, 0]) == pytest.approx(ours_phi[position], abs=1e-3)


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    with pytest.raises(StepError, match="at least two frames"):
        ctx = Context(str(tmp_path / "task"), {"params": {}})
        lines = [line for line in TOPOLOGY.read_text().splitlines() if line.startswith(("ATOM", "HETATM"))]
        coords = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
        single = tmp_path / "single.npy"
        np.save(single, (coords / 10.0)[None, ...])
        run(ctx, [{"name": "structure_md_dihedral_occupancy", "params": {"output": "dihedrals", "trajectory_path": str(single), "topology_path": str(TOPOLOGY)}}])
