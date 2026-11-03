"""structure_md_communication_path: DCCM and Dijkstra paths."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_communication_path import dccm, path_weights, shortest_path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_dccm_and_weights():
    matrix = np.array([[4.0, 2.0], [2.0, 4.0]])
    correlation = dccm(matrix)
    assert correlation[0, 1] == pytest.approx(0.5)
    weights = path_weights(correlation, 0.05)
    assert weights[0, 1] == pytest.approx(-np.log(0.5))
    assert np.all(np.diag(weights) == 0)


def test_shortest_path_chain():
    weights = np.array([
        [0.0, 1.0, 9.0],
        [1.0, 0.0, 1.0],
        [9.0, 1.0, 0.0],
    ])
    path, length = shortest_path(weights, 0, 2)
    assert path == [0, 1, 2]
    assert length == pytest.approx(2.0)


def test_scipy_oracle():
    scipy_sparse = pytest.importorskip("scipy.sparse.csgraph")
    rng = np.random.default_rng(0)
    base = rng.random((8, 3)) * 0.2
    matrix = base @ base.T + np.eye(8) * 0.5
    weights = path_weights(dccm(matrix), 0.0)
    weights = np.clip(weights, 0.0, 10.0)
    path, length = shortest_path(weights, 0, 7)
    distance = scipy_sparse.dijkstra(weights, directed=False, indices=0)[7]
    assert length == pytest.approx(distance, rel=1e-9)


def test_run_and_errors(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\nEND\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(4)
    frames = np.asarray([base + rng.normal(0.0, 0.3, base.shape) for _ in range(30)]) / 10.0
    path_npy = tmp_path / "traj.npy"
    np.save(path_npy, frames)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_communication_path", "params": {"trajectory_path": str(path_npy), "topology_path": str(topology), "source": 1, "target": 132, "min_correlation": 0.0}}])
    result = ctx["path"]
    assert result.data.shape[1] == 3
    assert result.info["path_residues"][0] == 1
    assert result.info["path_residues"][-1] == 132
    assert result.info["path_length"] == pytest.approx(result.info["scipy_distance"], rel=1e-5)
    with pytest.raises(StepError, match="must differ"):
        shortest_path(np.zeros((3, 3)), 1, 1)
    with pytest.raises(StepError, match="no path"):
        blocked = np.full((3, 3), np.inf)
        np.fill_diagonal(blocked, 0.0)
        shortest_path(blocked, 0, 2)
