"""sequence_rna_cofold_ensemble: two-strand ensemble statistics."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_cofold_ensemble import per_base_statistics

pytest.importorskip("RNA")


def test_per_base_partition():
    matrix = np.zeros((4, 4))
    matrix[0, 3] = matrix[3, 0] = 0.6
    matrix[0, 1] = matrix[1, 0] = 0.4
    stats = per_base_statistics(matrix, 2, 2)
    assert stats["inter"][0] == pytest.approx(0.6)
    assert stats["intra"][0] == pytest.approx(0.4)
    assert stats["unpaired"][0] == pytest.approx(0.0)
    assert stats["total_inter"] == pytest.approx(0.6)


def test_identity_and_mfe():
    from src.task.step.steps.sequence_rna_cofold_ensemble import cofold_ensemble

    result = cofold_ensemble("GGGAAACCC", "GGGAAACCC")
    assert result["matrix"].shape == (18, 18)
    stats = per_base_statistics(result["matrix"], 9, 9)
    total = stats["unpaired"] + stats["intra"] + stats["inter"]
    assert np.allclose(total, 1.0, atol=1e-6)
    assert result["energy"] < 0
    assert "&" not in result["structure"]


def test_run(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences(["GGGAAACCC", "GGGAAACCC"], "sequence", "position", "rna")
    run(ctx, [{"name": "sequence_rna_cofold_ensemble", "inputs": ["sequence"], "params": {"output": "cofold"}}])
    result = ctx["cofold"]
    assert result.dims == ["base", "statistic"]
    assert result.data.shape == (18, 3)
    assert result.info["mfe_energy_kcal"] < 0
    assert result.info["total_interstrand_probability"] >= 0.0
    with pytest.raises(StepError, match="exactly two strands"):
        ctx2 = Context(str(tmp_path / "task2"), {"params": {}})
        ctx2["sequence"] = encode_sequences(["GGGAAACCC"], "sequence", "position", "rna")
        run(ctx2, [{"name": "sequence_rna_cofold_ensemble", "inputs": ["sequence"], "params": {"output": "cofold"}}])
