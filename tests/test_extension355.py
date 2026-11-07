"""Tests for the QUAST assembly-metrics operator."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.assembly_stats import parse_report, parse_value

QUAST = os.environ.get("OPERON_QUAST") or shutil.which("quast")

REPORT = (
    "Assembly\tcontigs\n"
    "# contigs (>= 0 bp)\t4\n"
    "Largest contig\t40\n"
    "Total length (>= 0 bp)\t100\n"
    "N50\t30\n"
    "L50\t2\n"
    "GC (%)\t50.00\n"
)

FAKE = '''
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("-o") + 1])
out.mkdir(parents=True, exist_ok=True)
report = "Assembly\\tcontigs\\n# contigs (>= 0 bp)\\t4\\nLargest contig\\t40\\nTotal length (>= 0 bp)\\t100\\nN50\\t30\\nL50\\t2\\n"
(out / "report.tsv").write_text(report)
'''


def test_parse_value() -> None:
    assert parse_value("48502") == pytest.approx(48502.0)
    assert parse_value("48.502 kbp") == pytest.approx(48502.0)
    assert parse_value("1.5 Mbp") == pytest.approx(1_500_000.0)
    assert parse_value("1,234") == pytest.approx(1234.0)
    assert parse_value("N/A") is None
    assert parse_value("") is None


def test_parse_report() -> None:
    metrics = parse_report(REPORT)
    assert metrics["N50"] == pytest.approx(30.0)
    assert metrics["Total length (>= 0 bp)"] == pytest.approx(100.0)
    assert metrics["GC (%)"] == pytest.approx(50.0)
    assert metrics["# contigs (>= 0 bp)"] == pytest.approx(4.0)
    assert "Assembly" not in metrics


def test_run_with_fake_quast(tmp_path) -> None:
    binary = tmp_path / "quast.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ACGT" * 10, "ACGT" * 7], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["contigs"] = form
    run(
        ctx,
        [
            {
                "name": "assembly_stats",
                "inputs": ["contigs"],
                "params": {"quast_path": str(binary), "output": "metrics"},
            }
        ],
    )
    out = ctx["metrics"]
    assert out.dims == ["metric", "statistic"]
    assert out.data.shape == (5, 1)
    assert out.info["n50"] == pytest.approx(30.0)
    assert out.info["total_length"] == pytest.approx(100.0)
    assert out.info["n_contigs"] == pytest.approx(4.0)
    assert out.labels["metric"]["N50"] == 3


def test_run_errors(tmp_path) -> None:
    binary = tmp_path / "quast.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ACGT" * 10], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["contigs"] = form
    with pytest.raises(StepError, match="was not found"):
        run(
            ctx,
            [
                {
                    "name": "assembly_stats",
                    "inputs": ["contigs"],
                    "params": {"quast_path": str(tmp_path / "missing")},
                }
            ],
        )
    with pytest.raises(StepError, match="reference_path"):
        run(
            ctx,
            [
                {
                    "name": "assembly_stats",
                    "inputs": ["contigs"],
                    "params": {
                        "quast_path": str(binary),
                        "reference_path": str(tmp_path / "missing.fa"),
                    },
                }
            ],
        )


@pytest.mark.skipif(not QUAST, reason="QUAST is not available")
@pytest.mark.skipif(
    not os.environ.get("OPERON_REAL_ASSEMBLY"), reason="set OPERON_REAL_ASSEMBLY=1"
)
def test_real_quast_n50(tmp_path) -> None:
    contigs = ["ACGTACGTAC", "ACGT" * 5, "ACGT" * 7 + "AC", "ACGT" * 10]
    form = encode_sequences(contigs, "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["contigs"] = form
    run(
        ctx,
        [
            {
                "name": "assembly_stats",
                "inputs": ["contigs"],
                "params": {"quast_path": QUAST, "min_contig": 0, "threads": 4},
            }
        ],
    )
    out = ctx["metrics"]
    assert out.info["n50"] == pytest.approx(30.0)
    assert out.info["l50"] == pytest.approx(2.0)
    assert out.info["total_length"] == pytest.approx(100.0)
    assert out.info["n_contigs"] == pytest.approx(4.0)
