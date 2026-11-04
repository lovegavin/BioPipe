"""sequence_beta_propensity: Chou-Fasman hot spots."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_beta_propensity import beta_hotspots, beta_scores


def test_scores_and_hotspots():
    assert beta_scores("VI") == pytest.approx([1.70, 1.60])
    rows = beta_hotspots(beta_scores("VVVVV"), window=5, threshold=1.05, min_length=4)
    assert [(r["start"], r["end"], r["length"]) for r in rows] == [(1, 5, 5)]
    assert rows[0]["mean_score"] == pytest.approx(1.70)


def test_run_writes_table():
    form = encode_sequences(["VVVVV"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp286", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_beta_propensity", "inputs": ["sequence"], "params": {"output": "hotspots", "window": 5}}])
    assert ctx["hotspots"].info["n_hotspots"] == 1


def test_errors():
    with pytest.raises(StepError, match="outside the Chou-Fasman table"):
        beta_scores("X")
    with pytest.raises(StepError, match="shorter than the window"):
        beta_hotspots(beta_scores("VV"), window=5)
