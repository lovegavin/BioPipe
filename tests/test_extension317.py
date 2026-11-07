"""sequence_rna_cofold: RNAcofold parsing and equilibrium table."""

import shutil

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_cofold import parse_cofold, run_cofold

pytestmark = pytest.mark.skipif(shutil.which("RNAcofold") is None, reason="RNAcofold is not installed")

A = "GGGAAACCC"
B = "GGGAAACCC"


def test_parse_cofold_hand_case():
    text = run_cofold("RNAcofold", (A, B), (1.0, 1.0))
    record = parse_cofold(text)
    assert record["structure"].count("&") == 1
    assert record["mfe"] == pytest.approx(-7.10, abs=0.01)
    assert record["frequency"] == pytest.approx(1.76561, rel=1e-4)
    assert record["binding"] == pytest.approx(-3.51, abs=0.01)
    assert record["equilibrium"]["AB"] == pytest.approx(0.16118, rel=1e-3)


def test_validation_errors():
    with pytest.raises(StepError, match="non-RNA characters"):
        run_cofold("RNAcofold", ("ACGT!", B), (1.0, 1.0))
    with pytest.raises(StepError, match="concentrations must be positive"):
        run_cofold("RNAcofold", (A, B), (0.0, 1.0))
    with pytest.raises(StepError, match="was not found"):
        run_cofold("definitely-not-rnacofold", (A, B), (1.0, 1.0))


def test_operator_round_trip():
    form = encode_sequences([A, B], "sequence", "position", "rna")
    ctx = Context("/tmp/operon_test_rnacofold", {"params": {}})
    ctx["rna"] = form
    run(ctx, [{"name": "sequence_rna_cofold", "inputs": ["rna"], "params": {"output": "cofold", "concentration_a": 1.0, "concentration_b": 1.0}}])
    table = ctx["cofold"]
    assert table.data.shape == (1, 9)
    assert table.info["structure"].count("&") == 1
