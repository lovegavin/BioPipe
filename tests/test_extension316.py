"""sequence_rna_duplex: ViennaRNA duplex parsing and operator round trip."""

import shutil
import subprocess
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_duplex import parse_duplex, run_duplex

pytestmark = pytest.mark.skipif(shutil.which("RNAduplex") is None, reason="RNAduplex is not installed")

MIR = "UAGCUUAUCAGACUGAUGUUGA"
TARGET = "AACAUCAGUCUGAUAAGCUA"


def test_parse_duplex_line():
    text = "((((((((((((((((((((.&))))))))))))))))))))   1,21  :   1,20  (-31.90)"
    records = parse_duplex(text)
    assert len(records) == 1
    assert records[0]["start_a"] == 1 and records[0]["end_a"] == 21
    assert records[0]["start_b"] == 1 and records[0]["end_b"] == 20
    assert records[0]["energy"] == -31.90


def test_run_duplex_matches_cli():
    ours = parse_duplex(run_duplex("RNAduplex", (MIR, TARGET)))
    proc = subprocess.run(["RNAduplex"], input=MIR + "\n" + TARGET + "\n", capture_output=True, text=True)
    expected = parse_duplex(proc.stdout)
    assert len(ours) == len(expected)
    assert ours[0] == expected[0]
    assert ours[0]["energy"] < -20


def test_run_duplex_validation():
    with pytest.raises(StepError, match="exactly two sequences"):
        run_duplex("RNAduplex", (MIR,))
    with pytest.raises(StepError, match="non-RNA characters"):
        run_duplex("RNAduplex", ("ACGT!", TARGET))
    with pytest.raises(StepError, match="was not found"):
        run_duplex("definitely-not-rnaduplex", (MIR, TARGET))


def test_operator_round_trip():
    form = encode_sequences([MIR, TARGET], "sequence", "position", "rna")
    ctx = Context("/tmp/operon_test_rnaduplex", {"params": {}})
    ctx["rna"] = form
    run(ctx, [{"name": "sequence_rna_duplex", "inputs": ["rna"], "params": {"output": "duplexes"}}])
    table = ctx["duplexes"]
    assert table.data.shape[1] == 5
    assert table.info["best_energy"] == pytest.approx(-31.90, abs=0.01)
