"""sequence_rna_fold: ViennaRNA RNAfold wrapper."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_fold import clean_sequence, parse_output, run_rnafold


def test_clean_sequence_normalises_and_validates():
    assert clean_sequence("acgutn", "x") == "ACGUUN"
    assert clean_sequence("ACGT", "x") == "ACGU"
    with pytest.raises(StepError, match="non-nucleotide"):
        clean_sequence("ACGP", "x")
    with pytest.raises(StepError, match="is empty"):
        clean_sequence("   ", "x")


def test_parse_output_hand_case():
    text = "GCGCUUCGCCGCAAAAAA\n(((......)))...... ( -2.80)\n"
    records = parse_output(text, "x")
    assert len(records) == 1
    record = records[0]
    assert record["structure"] == "(((......)))......"
    assert record["mfe"] == pytest.approx(-2.80)
    assert record["n_pairs"] == 3
    assert record["gc"] == pytest.approx(10 / 18)


def test_run_matches_hand_computed_hairpin(tmp_path):
    pytest.importorskip("shutil")
    import shutil

    if shutil.which("RNAfold") is None:
        pytest.skip("RNAfold is not installed")
    records = run_rnafold(["GCGCUUCGCCGCAAAAAA"])
    assert records[0]["structure"] == "(((......)))......"
    assert records[0]["mfe"] == pytest.approx(-2.80, abs=0.01)


def test_runner_round_trip(tmp_path):
    import shutil

    if shutil.which("RNAfold") is None:
        pytest.skip("RNAfold is not installed")
    form = encode_sequences(["GCGCUUCGCCGCAAAAAA", "AAAA"], "sequence", "position", "rna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    run(ctx, [{"name": "sequence_rna_fold", "inputs": ["sequences"], "params": {"output": "folds"}}])
    result = ctx["folds"]
    assert result.dims == ["sequence", "statistic"]
    assert result.data.shape == (2, 5)
    assert result.data[0, 0] == pytest.approx(-2.80, abs=0.01)
    assert result.info["structures"][0] == "(((......)))......"


def test_errors(tmp_path):
    form = encode_sequences(["ACGU"], "sequence", "position", "rna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "sequence_rna_fold", "inputs": ["sequences"], "params": {"output": "folds", "rnafold_path": str(tmp_path / "missing")}}])
