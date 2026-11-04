"""structure_md_free_energy_landscape: histogram free-energy surface."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_free_energy_landscape import K_B_KJ, free_energy, project

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _trajectory(tmp_path, count=120, sigma=0.5, seed=1):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\nEND\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(seed)
    frames = np.asarray([base + rng.normal(0.0, sigma, base.shape) for _ in range(count)])
    path = tmp_path / "traj.npy"
    np.save(path, frames / 10.0)
    return path, topology, frames / 10.0


def test_analytic_gaussian_surface():
    rng = np.random.default_rng(0)
    samples = rng.normal(0.0, 1.0, (20000, 2))
    _, probability, energy = free_energy(samples, bins=25, temperature=300.0)
    finite = np.isfinite(energy)
    assert finite.sum() > 250
    assert np.nanmin(energy) == pytest.approx(0.0, abs=1e-9)
    centre = np.unravel_index(np.nanargmin(energy), energy.shape)
    near = energy[centre[0] + 3, centre[1]]
    far = energy[centre[0] + 6, centre[1]]
    assert 0.0 < near < far
    assert far / near == pytest.approx(4.0, rel=0.45)


def test_rotation_invariance(tmp_path):
    path, topology, frames = _trajectory(tmp_path, count=60)
    from src.task.step.steps.structure_md_pca import ca_indices, covariance, kabsch, load_frames

    selected = kabsch(load_frames(path)[:, ca_indices(topology, frames.shape[1]), :])
    matrix = covariance(selected)
    pc = project(selected, matrix)
    _, _, energy = free_energy(pc, bins=15, temperature=300.0)
    rotated = selected @ np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    pc2 = project(rotated, covariance(rotated))
    _, _, energy2 = free_energy(pc2, bins=15, temperature=300.0)
    a = np.sort(energy[np.isfinite(energy)])
    b = np.sort(energy2[np.isfinite(energy2)])
    assert a.shape == b.shape
    assert np.allclose(a, b, atol=1e-3)


def test_run_and_errors(tmp_path):
    path, topology, frames = _trajectory(tmp_path, count=60)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_free_energy_landscape", "params": {"trajectory_path": str(path), "topology_path": str(topology), "bins": 10, "temperature": 300.0}}])
    result = ctx["landscape"]
    assert result.dims == ["cell", "statistic"]
    assert result.info["probability_sum"] == pytest.approx(1.0, rel=1e-6)
    assert result.info["min_free_energy_kj"] == 0.0
    with pytest.raises(StepError, match="must be distinct"):
        run(ctx, [{"name": "structure_md_free_energy_landscape", "params": {"trajectory_path": str(path), "topology_path": str(topology), "pc1": 1, "pc2": 1}}])
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "structure_md_free_energy_landscape", "params": {"trajectory_path": str(path), "topology_path": str(topology), "temperature": -1.0}}])
