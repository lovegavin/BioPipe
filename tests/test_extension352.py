"""Tests for the tRNAscan-SE operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.trnascan_se import parse_output

REPORT = """Sequence\t\ttRNA\tBounds\ttRNA\tAnti\tIntron Bounds\tInf
Name    \ttRNA #\tBegin\tEnd\tType\tCodon\tBegin\tEnd\tScore\tNote
--------\t------\t-----\t------\t----\t-----\t-----\t----\t------\t------
contig1 \t1\t10 \t80\tAla\tAGC\t0\t0\t62.4\t
contig1 \t2\t200\t270\tPhe\tGAA\t210\t225\t71.1\t
"""

FAKE = r'''
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("-o") + 1])
out.write_text(
    "Sequence\ttRNA\tBounds\ttRNA\tAnti\tIntron Bounds\tInf\n"
    "Name    \ttRNA #\tBegin\tEnd\tType\tCodon\tBegin\tEnd\tScore\tNote\n"
    "--------\t------\t-----\t------\t----\t-----\t-----\t----\t------\t------\n"
    "query1  \t1\t10 \t80\tAla\tAGC\t0\t0\t62.4\t\n"
)
'''


def test_parse():
    trnas = parse_output(REPORT)
    assert len(trnas) == 2
    assert trnas[0]["isotype"] == "Ala" and trnas[0]["anticodon"] == "AGC"
    assert trnas[0]["start"] == 10 and trnas[0]["end"] == 80
    assert trnas[1]["intron_start"] == 210 and trnas[1]["intron_end"] == 225
    assert trnas[1]["score"] == pytest.approx(71.1)


def test_run(tmp_path):
    binary = tmp_path / "trnascan.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ATGC" * 300], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    run(ctx, [{"name": "trnascan_se", "inputs": ["dna"], "params": {
        "trnascan_path": str(binary), "output": "trnas"}}])
    out = ctx["trnas"]
    assert out.dims == ["trna", "statistic"]
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == 10 and out.data[0, 1] == 80
    assert out.info["n_trnas"] == 1
    assert out.info["isotypes"] == ["Ala"]


def test_run_errors(tmp_path):
    form = encode_sequences(["ATGC"], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "trnascan_se", "inputs": ["dna"], "params": {"mode": "weird"}}])
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "trnascan_se", "inputs": ["dna"], "params": {
            "trnascan_path": str(tmp_path / "missing")}}])


def test_real_trnascan_trna(tmp_path):
    import os
    import shutil

    if os.environ.get("OPERON_TRNA_REAL") != "1":
        pytest.skip("set OPERON_TRNA_REAL=1 to run the real tRNAscan-SE check")
    if shutil.which("tRNAscan-SE") is None:
        pytest.skip("tRNAscan-SE is not installed")
    form = encode_sequences(
        ["GCGGATTTAGCTCAGTTGGGAGAGCGCCAGACTGAAGATCTGGAGGTCCTGTGTTCGATCCACAGAACTCGCACCA"],
        "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    run(ctx, [{"name": "trnascan_se", "inputs": ["dna"], "params": {"mode": "general", "output": "trnas"}}])
    out = ctx["trnas"]
    assert out.info["n_trnas"] == 1
    assert out.info["trnas"][0]["isotype"] == "Phe"
    assert out.info["trnas"][0]["anticodon"] == "GAA"
