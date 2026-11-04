"""structure_lddt: lDDT against OpenFold's implementation."""

from pathlib import Path

import numpy as np
import pytest
import torch

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.reader import read_source
from src.task.step.steps.structure_tm_score import ca_map, match_residues
from src.task.step.steps.structure_lddt import lddt_scores, lddt_table

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"


def _form():
    return read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_identical_structures_have_perfect_scores():
    form = _form()
    first, second, shared = match_residues(ca_map(form, "field", "A"), ca_map(form, "field", "A"))
    scores, counts = lddt_scores(first, second)
    assert np.allclose(scores, 1.0, atol=1e-6)
    assert (counts > 0).all()


def test_matches_openfold_lddt_implementation():
    """OpenFold's differentiable lddt() is the authoritative reference."""

    pytest.importorskip("openfold")
    from openfold.utils.loss import lddt

    form = _form()
    first, second, shared = match_residues(ca_map(form, "field", "A"), ca_map(form, "field", "B"))
    rng = np.random.default_rng(11)
    mobile = first + rng.normal(0.0, 0.8, first.shape)
    ours, _counts = lddt_scores(mobile, second, cutoff=15.0)
    predicted = torch.as_tensor(mobile[None, :, :], dtype=torch.float32)
    reference = torch.as_tensor(second[None, :, :], dtype=torch.float32)
    mask = torch.ones((1, len(shared), 1), dtype=torch.float32)
    oracle = lddt(predicted, reference, mask, cutoff=15.0, per_residue=True).numpy().reshape(-1)
    assert np.allclose(ours, oracle, atol=1e-4)


def test_run_writes_per_residue_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    run(ctx, [{"name": "structure_lddt", "inputs": ["pdb"], "params": {"output": "lddt", "reference_path": str(FIXTURE), "model_chains": "A", "reference_chains": "A"}}])
    result = ctx["lddt"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape[0] > 100
    assert 0.0 <= result.info["mean_lddt"] <= 1.0
    assert result.data[0, 0] == pytest.approx(1.0, abs=1e-5)


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "structure_lddt", "inputs": ["pdb"], "params": {"output": "lddt", "reference_path": str(tmp_path / "nope.pdb")}}])
    with pytest.raises(StepError, match="at least two atoms"):
        lddt_scores(np.zeros((1, 3)), np.zeros((1, 3)))
