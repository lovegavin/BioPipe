"""Tests for the Flye de novo assembly operator."""

from __future__ import annotations

import os
import random
import shutil
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.flye_assemble import n50, parse_assembly_info, parse_fasta

FIXTURES = Path(__file__).parent / "fixtures"
FLYE = os.environ.get("OPERON_FLYE") or shutil.which("flye")

FAKE = '''
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--out-dir") + 1])
out.mkdir(parents=True, exist_ok=True)
header = "#seq_name\\tlength\\tcov.\\tcirc.\\trepeat\\tmult.\\talt_group\\tgraph_path"
row1 = "contig_1\\t120\\t10\\tN\\tN\\t1\\t*\\t*,1,*"
row2 = "contig_2\\t80\\t5\\tY\\tN\\t1\\t*\\t*,1,*"
(out / "assembly_info.txt").write_text(header + "\\n" + row1 + "\\n" + row2 + "\\n")
(out / "assembly.fasta").write_text(">contig_1\\n" + "ACGT" * 30 + "\\n>contig_2\\n" + "ACGT" * 20 + "\\n")
'''


def test_n50_hand() -> None:
    assert n50([10, 20, 30, 40]) == (30, 2)
    assert n50([100, 50, 50]) == (100, 1)
    assert n50([]) == (0, 0)


def test_parse_assembly_info() -> None:
    header = "#seq_name\tlength\tcov.\tcirc.\trepeat\tmult.\talt_group\tgraph_path\n"
    text = header + "contig_1\t47913\t32\tN\tN\t1\t*\t*,1,*\ncontig_2\t1000\t5\tY\tN\t1\t*\t*,1,*\n"
    records = parse_assembly_info(text)
    assert [record["length"] for record in records] == [47913, 1000]
    assert records[0]["coverage"] == pytest.approx(32.0)
    assert records[0]["is_circular"] == 0.0
    assert records[1]["is_circular"] == 1.0


def test_parse_fasta() -> None:
    records = parse_fasta(">a desc\nACGT\n>b\nTTTT\n")
    assert records == [("a", "ACGT"), ("b", "TTTT")]


def test_run_with_fake_binary(tmp_path) -> None:
    binary = tmp_path / "flye.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ACGT" * 10], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["reads"] = form
    run(
        ctx,
        [
            {
                "name": "flye_assemble",
                "inputs": ["reads"],
                "params": {"flye_path": str(binary), "genome_size": "1k", "output": "assembly"},
            }
        ],
    )
    out = ctx["assembly"]
    assert out.dims == ["contig", "statistic"]
    assert out.data.shape == (2, 3)
    assert out.info["n_contigs"] == 2
    assert out.info["total_length"] == 200
    assert out.info["n50"] == 120
    assert out.info["l50"] == 1
    assert out.labels["contig"] == {"contig_1": 0, "contig_2": 1}


def test_run_errors(tmp_path) -> None:
    form = encode_sequences(["ACGT" * 10], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["reads"] = form
    with pytest.raises(StepError, match="was not found"):
        run(
            ctx,
            [
                {
                    "name": "flye_assemble",
                    "inputs": ["reads"],
                    "params": {"flye_path": str(tmp_path / "missing")},
                }
            ],
        )


def simulate_reads(genome: str, coverage: int = 30, read_length: int = 6000, seed: int = 7) -> list[str]:
    """Simulate error-prone long reads from a genome (deterministic)."""

    rng = random.Random(seed)
    count = max(1, int(len(genome) * coverage / read_length))
    reads: list[str] = []
    for _ in range(count):
        start = rng.randrange(0, max(1, len(genome) - read_length))
        piece = list(genome[start : start + read_length])
        for index in range(len(piece)):
            if rng.random() < 0.02:
                piece[index] = rng.choice("ACGT")
        reads.append("".join(piece))
    return reads


@pytest.mark.skipif(not FLYE, reason="Flye is not available")
@pytest.mark.skipif(
    not os.environ.get("OPERON_REAL_ASSEMBLY"), reason="set OPERON_REAL_ASSEMBLY=1"
)
def test_real_flye_from_simulated_reads(tmp_path) -> None:
    genome = "".join(
        line.strip() for line in (FIXTURES / "lambda_genome.fa").read_text().splitlines() if not line.startswith(">")
    )
    reads = simulate_reads(genome)
    form = encode_sequences(reads, "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["reads"] = form
    run(
        ctx,
        [
            {
                "name": "flye_assemble",
                "inputs": ["reads"],
                "params": {
                    "flye_path": FLYE,
                    "mode": "nano-raw",
                    "genome_size": "48k",
                    "threads": 4,
                    "output": "assembly",
                },
            }
        ],
    )
    out = ctx["assembly"]
    assert out.info["n_contigs"] >= 1
    assert out.info["total_length"] > 40000
    assert out.info["n50"] > 10000
    assert out.info["largest"] > 40000
