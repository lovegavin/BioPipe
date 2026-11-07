"""Tests for the Rfam cmscan operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.rfam_scan import parse_tblout

TBL = (
    "# target name   accession   query name   accession   mdl   mdl from   mdl to   seq from   seq to   strand   trunc   pass   gc   bias   score   E-value   inc   description\n"
    "RF00005   RF00005   query1   -   cm   2   70   5   73   +   no   1   0.5   0.1   45.2   1e-12   !   tRNA\n"
)

FAKE = r'''
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--tblout") + 1])
out.write_text(
    "RF00005   RF00005   query1   -   cm   2   70   5   73   +   no   1   0.5   0.1   45.2   1e-12   !   tRNA\n"
)
'''


def test_parse():
    hits = parse_tblout(TBL)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["family"] == "RF00005" and hit["accession"] == "RF00005"
    assert hit["start"] == 5 and hit["end"] == 73 and hit["strand"] == 1
    assert hit["score"] == pytest.approx(45.2)
    assert hit["evalue"] == pytest.approx(1e-12)
    assert hit["description"] == "tRNA"


def test_run(tmp_path):
    binary = tmp_path / "cmscan.py"
    binary.write_text(FAKE, encoding="utf-8")
    cm = tmp_path / "Rfam.cm"
    cm.write_text("model")
    form = encode_sequences(["GCGGATTTAGCTCAGTTGGGAGAGCGCCAGACTGAAGATCTGGAGGTCCTGTGTTCGATCCACAGAACTCGCACCA"],
                            "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["rna"] = form
    run(ctx, [{"name": "rfam_scan", "inputs": ["rna"], "params": {
        "cmscan_path": str(binary), "rfam_cm": str(cm), "output": "hits"}}])
    out = ctx["hits"]
    assert out.dims == ["hit", "statistic"]
    assert out.data.shape == (1, 8)
    assert out.data[0, 2] == 69
    assert out.info["n_hits"] == 1
    assert out.info["families"] == ["RF00005"]


def test_run_errors(tmp_path):
    form = encode_sequences(["ACGU"], "sequence", "position", "rna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["rna"] = form
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "rfam_scan", "inputs": ["rna"], "params": {
            "rfam_cm": str(tmp_path / "missing.cm")}}])
    cm = tmp_path / "Rfam.cm"
    cm.write_text("model")
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "rfam_scan", "inputs": ["rna"], "params": {
            "cmscan_path": str(tmp_path / "missing"), "rfam_cm": str(cm)}}])


def test_real_rfam_trna(tmp_path):
    import os
    import shutil
    from pathlib import Path

    if os.environ.get("OPERON_RFAM_REAL") != "1":
        pytest.skip("set OPERON_RFAM_REAL=1 to run the real Rfam scan")
    cm = Path("/home/gavin/tools/rfam/Rfam.cm")
    if shutil.which("cmscan") is None or not cm.is_file():
        pytest.skip("cmscan or the Rfam covariance models are not installed")
    form = encode_sequences(
        ["GCGGATTTAGCTCAGTTGGGAGAGCGCCAGACTGAAGATCTGGAGGTCCTGTGTTCGATCCACAGAACTCGCACCA"],
        "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["rna"] = form
    run(ctx, [{"name": "rfam_scan", "inputs": ["rna"], "params": {
        "rfam_cm": str(cm), "evalue": 1e-5, "output": "hits"}}])
    out = ctx["hits"]
    assert out.info["n_hits"] >= 1
    assert "RF00005" in {hit["accession"] for hit in out.info["hits"]}
