"""structure_md_markov_states: transition matrices and implied timescales."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_markov_states import (
    implied_timescales,
    transition_counts,
    transition_matrix,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_transition_matrix_two_state():
    labels = np.array([1, 1, 2, 2, 1, 2, 1, 1, 2, 2])
    counts = transition_counts(labels, 2, 1)
    matrix = transition_matrix(counts)
    assert matrix.shape == (2, 2)
    assert np.allclose(matrix.sum(axis=1), 1.0)
    assert matrix[0, 1] == pytest.approx(3.0 / 5.0)
    assert matrix[1, 0] == pytest.approx(2.0 / 4.0)


def test_implied_timescales_analytic():
    p_ab, p_ba = 0.1, 0.2
    matrix = np.array([[1 - p_ab, p_ab], [p_ba, 1 - p_ba]])
    timescales = implied_timescales(matrix, 1, 0.5, 1)
    expected = -0.5 / np.log(1 - p_ab - p_ba)
    assert timescales[0] == pytest.approx(expected, rel=1e-9)
    with pytest.raises(StepError, match="lag must be at least 1"):
        transition_counts(np.array([1, 2]), 2, 0)
    with pytest.raises(StepError, match="pseudo count"):
        transition_matrix(np.eye(2), pseudo=-1.0)


def test_run(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(5)
    frames = []
    for group in range(2):
        moved = base.copy()
        moved[len(base) // 2:] += np.array([0.0, 0.0, 5.0 * group])
        for _ in range(12):
            frames.append(moved + rng.normal(0.0, 0.1, moved.shape))
    path = tmp_path / "traj.npy"
    np.save(path, np.asarray(frames) / 10.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_markov_states", "params": {"trajectory_path": str(path), "topology_path": str(topology), "cutoff": 1.0, "lag_frames": 2, "frame_time_ps": 0.5}}])
    result = ctx["states"]
    assert result.dims == ["state", "statistic"]
    assert result.info["n_states"] == 2
    assert result.info["n_transitions"] == 22
    matrix = np.asarray(result.info["transition_matrix"])
    assert np.allclose(matrix.sum(axis=1), 1.0)
    assert len(result.info["implied_timescales_ps"]) >= 1
    assert result.info["implied_timescales_ps"][0] > 0
