"""structure_md_pca: covariance eigenmodes of a trajectory."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_pca import ca_indices, covariance, kabsch, load_frames, pca_modes

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _topology(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    path = tmp_path / "top.pdb"
    path.write_text("\n".join(lines) + "\nEND\n")
    return path, lines


def _frames(lines, count=30, sigma=0.3, seed=0):
    rng = np.random.default_rng(seed)
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    frames = []
    for _ in range(count):
        frames.append(base + rng.normal(0.0, sigma, base.shape))
    return np.asarray(frames) / 10.0


def test_kabsch_invariance(tmp_path):
    topology, lines = _topology(tmp_path)
    frames = _frames(lines)
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    selected = load_frames(path)[:, ca_indices(topology, len(lines)), :]
    first = kabsch(selected)
    rotated = selected @ np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    second = kabsch(rotated)
    values_a, _ = pca_modes(covariance(first), 5)
    values_b, _ = pca_modes(covariance(second), 5)
    assert np.allclose(values_a, values_b, rtol=1e-8, atol=1e-10)


def test_prody_pca_oracle(tmp_path):
    prody = pytest.importorskip("prody")
    mdtraj = pytest.importorskip("mdtraj")
    topology, lines = _topology(tmp_path)
    frames = _frames(lines)
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    selected = load_frames(path)[:, ca_indices(topology, len(lines)), :]
    aligned = kabsch(selected)
    values, _ = pca_modes(covariance(aligned), 5)

    full = mdtraj.load(str(topology))
    selected_topology = full.atom_slice(ca_indices(topology, len(lines))).topology
    traj = mdtraj.Trajectory(aligned / 10.0, topology=selected_topology)
    dcd = tmp_path / "aligned.dcd"
    traj.save_dcd(str(dcd))
    coordinates = prody.parseDCD(str(dcd))
    pca = prody.PCA("traj")
    pca.buildCovariance(coordinates)
    pca.calcModes(None)
    expected = np.sort(pca.getEigvals())[::-1][:5]
    ours = values / values.sum()
    theirs = expected / expected.sum()
    assert np.allclose(ours, theirs, rtol=2e-3, atol=1e-5)


def test_run_and_errors(tmp_path):
    topology, lines = _topology(tmp_path)
    frames = _frames(lines)
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_pca", "params": {"trajectory_path": str(path), "topology_path": str(topology), "n_modes": 5}}])
    result = ctx["modes"]
    assert result.dims == ["mode", "statistic"]
    assert result.data.shape[0] <= 5
    assert 0.0 < float(result.data[-1, 2]) <= 1.0001
    assert result.info["n_modes"] == result.data.shape[0]
    single = tmp_path / "single.npy"
    np.save(single, np.array([[[0.0, 0.0, 0.0]]]))
    with pytest.raises(StepError, match="at least two frames"):
        load_frames(single)
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
