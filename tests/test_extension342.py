"""structure_md_dssp_transitions: coarse secondary-structure kinetics."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_dssp_transitions import coarse_state, transition_rows, transition_totals

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_coarse_state():
    assert coarse_state("H") == 0
    assert coarse_state("G") == 0
    assert coarse_state("E") == 1
    assert coarse_state("B") == 1
    assert coarse_state("-") == 2
    assert coarse_state("T") == 2


def test_transition_totals_and_rows():
    matrix = np.array([[0, 1, 2]])
    counts = transition_totals(matrix, 1)
    assert counts.sum() == 2
    assert counts[1, 2] == 1
    rows = transition_rows(matrix, ["A:ALA:1"], lag=1, frame_time_ps=0.5)
    assert rows[0]["p_coil"] == pytest.approx(1.0 / 3.0)
    assert rows[0]["transitions"] == 2
    assert rows[0]["dominant"] == "helix"
    with pytest.raises(StepError, match="lag must be at least 1"):
        transition_totals(matrix, 0)


@pytest.mark.skipif(shutil.which("mkdssp") is None, reason="mkdssp is required")
def test_run(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(4)
    frames = np.asarray([base + rng.normal(0.0, 0.05, base.shape) for _ in range(4)]) / 10.0
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_dssp_transitions", "params": {"trajectory_path": str(path), "topology_path": str(topology)}}])
    result = ctx["transitions"]
    assert result.dims == ["residue", "statistic"]
    assert result.info["n_residues"] == 132
    assert result.data.shape[0] == 132
    assert np.allclose(result.data[:, :3].sum(axis=1), 1.0, atol=1e-5)
