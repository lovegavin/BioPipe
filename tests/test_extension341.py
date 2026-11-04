"""structure_md_rotamer_states: chi1 rotamer classification."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_rotamer_states import ROTAMERS, rotamer, rotamer_rows

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def test_rotamer_classification():
    assert rotamer(60.0) == "g+"
    assert rotamer(179.0) == "t"
    assert rotamer(-60.0) == "g-"
    assert rotamer(-15.0) == "g-"
    assert rotamer(-179.0) == "t"


def test_rotamer_rows_entropy():
    records = [{"label": "A:ALA:1", "indices": (0, 1, 2, 3)}]
    codes = np.array([[0, 1, 0, 1]])
    angles = np.array([[60.0, 180.0, 60.0, 180.0]])
    rows = rotamer_rows(records, angles, codes)
    assert rows[0]["p_gplus"] == pytest.approx(0.5)
    assert rows[0]["p_trans"] == pytest.approx(0.5)
    assert rows[0]["entropy"] == pytest.approx(np.log(2.0))
    assert rows[0]["transitions"] == 3


def test_run(tmp_path):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(2)
    frames = np.asarray([base + rng.normal(0.0, 0.02, base.shape) for _ in range(10)]) / 10.0
    path = tmp_path / "traj.npy"
    np.save(path, frames)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_rotamer_states", "params": {"trajectory_path": str(path), "topology_path": str(topology)}}])
    result = ctx["rotamers"]
    assert result.dims == ["residue", "statistic"]
    assert result.info["n_residues"] > 10
    assert np.allclose(result.data[:, :3].sum(axis=1), 1.0, atol=1e-5)
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "structure_md_rotamer_states", "params": {"trajectory_path": str(path), "topology_path": str(tmp_path / "missing.pdb")}}])
