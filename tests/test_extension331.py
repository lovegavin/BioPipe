"""structure_md_quasiharmonic_entropy: Schlitter configurational entropy."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_quasiharmonic_entropy import (
    R_GAS,
    entropy_from_covariance,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_analytic_harmonic_entropy():
    sigma2 = 0.25
    matrix = np.diag([sigma2] * 6)
    total, contributions, values = entropy_from_covariance(matrix)
    expected = 6 * 0.5 * (1.0 + np.log(2.0 * np.pi * sigma2))
    assert total == pytest.approx(expected, rel=1e-12)
    assert contributions.sum() == pytest.approx(total, rel=1e-12)
    with pytest.raises(StepError, match="no non-zero mode"):
        entropy_from_covariance(np.zeros((3, 3)))


def _trajectory(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\nEND\n")
    rng = np.random.default_rng(3)
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    frames = np.asarray([base + rng.normal(0.0, 0.4, base.shape) for _ in range(40)]) / 10.0
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    return path, topology


def test_run_and_invariance(tmp_path):
    path, topology = _trajectory(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    params = {"trajectory_path": str(path), "topology_path": str(topology), "n_modes": 4}
    run(ctx, [{"name": "structure_md_quasiharmonic_entropy", "params": params}])
    result = ctx["entropy"]
    assert result.dims == ["mode", "statistic"]
    assert "total" in result.labels["mode"]
    total = result.info["total_entropy_kb"]
    assert result.info["entropy_kj_mol_k"] == pytest.approx(total * R_GAS / 1000.0, rel=1e-5)
    assert result.info["n_atoms"] == 132
    frames = np.load(path)
    rotated = frames @ np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    np.save(tmp_path / "rot.npy", rotated)
    ctx2 = Context(str(tmp_path / "task2"), {"params": {}})
    params2 = dict(params, trajectory_path=str(tmp_path / "rot.npy"))
    run(ctx2, [{"name": "structure_md_quasiharmonic_entropy", "params": params2}])
    assert ctx2["entropy"].info["total_entropy_kb"] == pytest.approx(total, rel=1e-4)
