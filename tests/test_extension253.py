"""Tests for the HMMER domain annotation operator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.hmmer_domains import HmmerDomainsStep, parse_domtbl, write_fasta

DOMTBL = (
    "#                                                                            --- full sequence ---  --- this domain ---\n"
    "PF00069.20  PF00069.20  260  query1  -  413  2.3e-15  50.2  0.1   1  1  2.3e-15  2.3e-15  50.2  0.1   5  120  6  121  6  121  0.96  Protein kinase domain\n"
    "PF00001.10  PF00001.10  300  query1  -  413  1.0e-03   8.0  0.0   1  1  1.0e-03  1.0e-03   8.0  0.0  10  200  30  240  30  240  0.60  Other domain\n"
)

FAKE = r'''
import pathlib, sys
args = sys.argv[1:]

def value(flag):
    return args[args.index(flag) + 1]

pathlib.Path(value("--domtblout")).write_text("""PF00069.20 PF00069.20 260 query1 - 413 2.3e-15 50.2 0.1 1 1 2.3e-15 2.3e-15 50.2 0.1 5 120 6 121 6 121 0.96 Protein kinase domain
""")
'''


def test_parse_domtbl(tmp_path) -> None:
    records = parse_domtbl(DOMTBL)
    assert len(records) == 2
    first = records[0]
    assert first["target"] == "PF00069.20"
    assert first["query"] == "query1"
    assert first["evalue"] == pytest.approx(2.3e-15)
    assert first["score"] == pytest.approx(50.2)
    assert (first["hmm_from"], first["hmm_to"]) == (5, 120)
    assert (first["ali_from"], first["ali_to"]) == (6, 121)
    assert (first["env_from"], first["env_to"]) == (6, 121)
    fasta = tmp_path / "queries.faa"
    write_fasta(["MKV"], fasta)
    assert fasta.read_text(encoding="utf-8") == ">query1\nMKV\n"


def test_run(tmp_path) -> None:
    binary = tmp_path / "hmmscan.py"
    binary.write_text(FAKE, encoding="utf-8")
    hmm = tmp_path / "Pfam-A.hmm"
    hmm.write_bytes(b"HMMER3/f\n")
    form = encode_sequences(["MKV"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    run(
        ctx,
        [
            {
                "name": "hmmer_domains",
                "inputs": ["protein"],
                "params": {"hmmscan_path": str(binary), "hmm_path": str(hmm), "output": "domains"},
            }
        ],
    )
    out = ctx["domains"]
    assert out.dims == ["domain", "statistic"]
    assert out.data.shape == (1, 8)
    assert out.info["n_domains"] == 1
    assert out.info["n_targets"] == 1
    assert out.info["domains"][0]["target"] == "PF00069.20"


def test_run_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPERON_PFAM_HMM", raising=False)
    form = encode_sequences(["MKV"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    with pytest.raises(StepError, match="hmm_path is required"):
        run(ctx, [{"name": "hmmer_domains", "inputs": ["protein"], "params": {}}])
    hmm = tmp_path / "Pfam-A.hmm"
    hmm.write_bytes(b"x")
    with pytest.raises(StepError, match="was not found on PATH"):
        run(ctx, [{"name": "hmmer_domains", "inputs": ["protein"], "params": {"hmm_path": str(hmm), "hmmscan_path": str(tmp_path / "nope")}}])
    empty = tmp_path / "empty.py"
    empty.write_text("import pathlib, sys\nargs = sys.argv[1:]\npathlib.Path(args[args.index('--domtblout') + 1]).write_text('')\n", encoding="utf-8")
    with pytest.raises(StepError, match="no domain above"):
        run(ctx, [{"name": "hmmer_domains", "inputs": ["protein"], "params": {"hmm_path": str(hmm), "hmmscan_path": str(empty)}}])


def test_real_hmmscan_when_available():
    import os
    import shutil

    binary = shutil.which("hmmscan")
    hmm = os.environ.get("OPERON_PFAM_HMM", "")
    if not binary or not hmm or not os.path.isfile(hmm):
        pytest.skip("OPERON_PFAM_HMM or hmmscan is not available")

    from src.task.context import Context
    from src.task.runner import run
    from src.task.step.steps._sequence_common import encode_sequences

    sequence = (
        "VQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYYADSVKGRFTISRDNAKSTVYLQMNSLKPEDTAIYYCAADSTIYSTTYWGQGTQVTVSS"
    )
    form = encode_sequences([sequence], "sequence", "position", "protein")
    import tempfile

    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["sequence"] = form
    run(
        ctx,
        [
            {
                "name": "hmmer_domains",
                "inputs": ["sequence"],
                "params": {"output": "domains", "hmm_path": hmm, "hmmscan_path": binary, "cpu": 2},
            }
        ],
    )
    result = ctx["domains"]
    assert result.data.shape[0] >= 1
    labels = list(result.labels["domain"])
    assert any(label.startswith(("V-set", "I-set", "Ig_")) for label in labels)
