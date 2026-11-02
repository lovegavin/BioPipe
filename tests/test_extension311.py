"""sequence_rna_ensemble: RNAfold partition-function wrapper."""

from pathlib import Path
import shutil

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_ensemble import parse_ensemble_output, run_rnafold_ensemble

OUTPUT = """GCGCUUCGCCGCAAAAAA
(((......)))...... ( -2.80)
(((......)))...... [ -3.07]
(((......)))...... { -2.80 d=0.99}
 frequency of mfe structure in ensemble 0.64388; ensemble diversity 1.69
"""


def test_parse_ensemble_output_hand_case():
    records = parse_ensemble_output(OUTPUT, "x")
    assert len(records) == 1
    record = records[0]
    assert record["mfe"] == pytest.approx(-2.80)
    assert record["ensemble"] == pytest.approx(-3.07)
    assert record["mea_energy"] == pytest.approx(-2.80)
    assert record["mea_diversity"] == pytest.approx(0.99)
    assert record["mfe_frequency"] == pytest.approx(0.64388)
    assert record["ensemble_diversity"] == pytest.approx(1.69)
    assert record["n_pairs"] == 3


def test_parse_two_sequences():
    text = OUTPUT + "GGGAAACCC\n(((.....))) ( -1.20)\n(((.....))) [ -1.40]\n(((.....))) { -1.20 d=0.10}\n frequency of mfe structure in ensemble 0.9; ensemble diversity 0.5\n"
    records = parse_ensemble_output(text, "x")
    assert [round(record["mfe"], 2) for record in records] == [-2.80, -1.20]


def test_run_matches_cli_when_available():
    if shutil.which("RNAfold") is None:
        pytest.skip("RNAfold is not installed")
    records = run_rnafold_ensemble(["GCGCUUCGCCGCAAAAAA"])
    assert records[0]["mfe"] == pytest.approx(-2.80, abs=0.01)
    assert records[0]["mfe_frequency"] == pytest.approx(0.64388, abs=1e-3)


def test_runner_round_trip(tmp_path):
    if shutil.which("RNAfold") is None:
        pytest.skip("RNAfold is not installed")
    form = encode_sequences(["GCGCUUCGCCGCAAAAAA"], "sequence", "position", "rna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    run(ctx, [{"name": "sequence_rna_ensemble", "inputs": ["sequences"], "params": {"output": "ensembles"}}])
    result = ctx["ensembles"]
    assert result.dims == ["sequence", "statistic"]
    assert result.data.shape == (1, 7)
    assert result.info["mfe_structures"][0] == "(((......)))......"


def test_errors(tmp_path):
    form = encode_sequences(["ACGU"], "sequence", "position", "rna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "sequence_rna_ensemble", "inputs": ["sequences"], "params": {"output": "ensembles", "rnafold_path": str(tmp_path / "missing")}}])
