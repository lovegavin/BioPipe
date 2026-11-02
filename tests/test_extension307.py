"""structure_openmm_md_rmsf: short MD against mdtraj."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_openmm_md_rmsf import rmsf_from_frames, radius_of_gyration, simulate

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"


def test_rmsf_of_a_rigid_trajectory_is_zero():
    frames = np.tile(np.arange(12, dtype=float).reshape(4, 3)[None, :, :], (3, 1, 1))
    assert np.allclose(rmsf_from_frames(frames), 0.0)
    rg = radius_of_gyration(frames)
    assert rg.shape == (3,)
    assert np.allclose(rg, rg[0])


def test_rmsf_matches_mdtraj_on_a_real_short_run(tmp_path):
    pytest.importorskip("mdtraj")
    pytest.importorskip("openmm")
    import mdtraj as md

    path = tmp_path / "model.pdb"
    path.write_text(FIXTURE.read_text())
    result = simulate(path, chains="A", steps=200, report_interval=50, workdir=tmp_path / "run")
    frames = np.load(result["trajectory"])
    topology = md.load(result["prepared_pdb"]).topology.subset(result["ca_indices"])
    ca = md.Trajectory(frames, topology)
    oracle = md.rmsf(ca, ca, frame=0, parallel=False)
    assert np.allclose(result["rmsf"], oracle, atol=2e-3)


def test_run_writes_flexibility_table(tmp_path):
    pytest.importorskip("openmm")
    pytest.importorskip("pdbfixer")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    run(ctx, [{"name": "structure_openmm_md_rmsf", "inputs": ["pdb"], "params": {"output": "flexibility", "chains": "A", "steps": 200, "report_interval": 50}}])
    result = ctx["flexibility"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape[0] > 100
    assert result.info["mean_rmsf_nm"] >= 0.0
    assert result.info["n_frames"] == 4


def test_errors(tmp_path):
    pytest.importorskip("openmm")
    pytest.importorskip("pdbfixer")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    with pytest.raises(StepError, match="not in the structure"):
        run(ctx, [{"name": "structure_openmm_md_rmsf", "inputs": ["pdb"], "params": {"output": "flexibility", "chains": "Z", "steps": 100}}])
