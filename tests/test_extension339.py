"""structure_md_tica: time-lagged covariance eigenproblem."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_tica import covariance_matrices, implied_timescales, tica_eigenvalues

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_ar1_recovers_eigenvalue():
    rng = np.random.default_rng(0)
    values = [0.0]
    for _ in range(4000):
        values.append(0.9 * values[-1] + rng.normal(0.0, 0.1))
    data = np.asarray(values)[:, None, None]
    instantaneous, lagged = covariance_matrices(data, 1)
    eigenvalues = tica_eigenvalues(instantaneous, lagged)
    assert eigenvalues[0] == pytest.approx(0.9, abs=0.02)


def test_implied_timescale_analytic():
    timescales = implied_timescales(np.array([0.9, 0.5]), 1, 0.2, 2)
    assert timescales[0] == pytest.approx(-0.2 / np.log(0.9), rel=1e-12)
    with pytest.raises(StepError, match="frame_time_ps must be positive"):
        implied_timescales(np.array([0.9]), 1, 0.0)
    with pytest.raises(StepError, match="no variance"):
        tica_eigenvalues(np.zeros((2, 2)), np.zeros((2, 2)))


def test_run(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(1)
    frames = np.asarray([base + rng.normal(0.0, 0.2, base.shape) for _ in range(40)]) / 10.0
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_tica", "params": {"trajectory_path": str(path), "topology_path": str(topology), "lag_frames": 2, "frame_time_ps": 0.5, "n_modes": 2}}])
    result = ctx["components"]
    assert result.dims == ["mode", "statistic"]
    assert result.data.shape == (2, 2)
    assert 0.0 < float(result.data[0, 0]) <= 1.1
    assert result.info["lag_frames"] == 2
    assert result.info["eigenvalues"]
    assert result.data.shape[1] == 2
