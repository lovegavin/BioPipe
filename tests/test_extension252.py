"""Tests for the Prodigal gene prediction operator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.prodigal_genes import (
    ProdigalGenesStep,
    parse_gff,
    parse_proteins,
    partial_code,
    write_fasta,
)

GFF = (
    "##gff-version 3\n"
    "contig1\tProdigal\tCDS\t1\t9\t.\t+\t0\tID=1_1;partial=00;\n"
    "contig1\tProdigal\tCDS\t21\t50\t.\t-\t0\tID=1_2;partial=10;\n"
)
PROTEINS = ">1_1 # 1 # 9 # 1 # ID=1_1;partial=00;\nMK\n>1_2 # 21 # 50 # -1\nMKV*\n"

FAKE = r'''
import pathlib, sys
args = sys.argv[1:]

def value(flag):
    return args[args.index(flag) + 1]

gff = "##gff-version 3\ncontig1\tProdigal\tCDS\t1\t9\t.\t+\t0\tID=1_1;partial=00;\n"
proteins = ">1_1 # 1 # 9 # 1 # ID=1_1;partial=00;\nMK\n"
pathlib.Path(value("-o")).write_text(gff)
pathlib.Path(value("-a")).write_text(proteins)
'''


def test_parsers(tmp_path) -> None:
    records = parse_gff(GFF)
    assert [record["id"] for record in records] == ["1_1", "1_2"]
    assert records[1]["strand"] == -1
    assert records[1]["start"] == 21 and records[1]["end"] == 50
    assert partial_code("00") == 0 and partial_code("10") == 2 and partial_code("11") == 3
    with pytest.raises(StepError, match="partial flag"):
        partial_code("07")
    assert parse_proteins(PROTEINS) == ["MK", "MKV*"]
    fasta = tmp_path / "seqs.fna"
    write_fasta(["ATGAAATAG"], fasta)
    assert fasta.read_text(encoding="utf-8").startswith(">contig1\nATGAAATAG")


def test_run(tmp_path) -> None:
    binary = tmp_path / "prodigal.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ATGAAATAG"], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    run(
        ctx,
        [
            {
                "name": "prodigal_genes",
                "inputs": ["dna"],
                "params": {"prodigal_path": str(binary), "output": "genes"},
            }
        ],
    )
    out = ctx["genes"]
    assert out.dims == ["gene", "statistic"]
    assert out.data.shape == (1, 5)
    row = out.data[0]
    assert row[0] == 1 and row[1] == 9 and row[2] == 1 and row[3] == 9 and row[4] == 0
    assert out.info["proteins"] == ["MK"]
    assert out.info["n_genes"] == 1


def test_run_errors(tmp_path) -> None:
    form = encode_sequences(["ATGAAATAG"], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    with pytest.raises(StepError, match="was not found on PATH"):
        run(ctx, [{"name": "prodigal_genes", "inputs": ["dna"], "params": {"prodigal_path": str(tmp_path / "nope")}}])
    binary = tmp_path / "empty.py"
    binary.write_text("import pathlib, sys\nargs = sys.argv[1:]\npathlib.Path(args[args.index('-o') + 1]).write_text('##gff-version 3\\n')\n", encoding="utf-8")
    with pytest.raises(StepError, match="no coding sequence"):
        run(ctx, [{"name": "prodigal_genes", "inputs": ["dna"], "params": {"prodigal_path": str(binary)}}])
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "prodigal_genes", "inputs": ["dna"], "params": {"mode": "weird"}}])


def test_real_lambda_genome(tmp_path):
    """Real Prodigal run on the phage lambda genome (48 502 bp)."""

    import os
    import shutil

    if os.environ.get("OPERON_PRODIGAL_REAL") != "1":
        pytest.skip("set OPERON_PRODIGAL_REAL=1 to run the real Prodigal check")
    if shutil.which("prodigal") is None:
        pytest.skip("prodigal is not installed")
    from src.task.step.steps._sequence_common import encode_sequences

    fixture = Path(__file__).resolve().parent / "fixtures" / "lambda_genome.fa"
    sequence = "".join(line.strip() for line in fixture.read_text().splitlines() if not line.startswith(">"))
    form = encode_sequences([sequence], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["genome"] = form
    run(ctx, [{"name": "prodigal_genes", "inputs": ["genome"], "params": {"output": "genes"}}])
    table = ctx["genes"]
    assert table.info["n_genes"] == 61
    assert table.info["n_partial"] == 0
    labels = sorted(table.labels["gene"], key=table.labels["gene"].get)
    row = table.data[0]
    assert float(row[0]) == pytest.approx(191, abs=0.5)
    assert float(row[1]) == pytest.approx(736, abs=0.5)
    assert float(row[2]) == pytest.approx(1)
    assert len(labels) == 61
