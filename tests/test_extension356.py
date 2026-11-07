"""Tests for the minced CRISPR-array operator."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.crispr_array_detect import parse_crisprs

MINCED = os.environ.get("OPERON_MINCED") or shutil.which("minced")
FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE = """Sequence 'NC_000913.3_crispr1' (562 bp)

CRISPR 1   Range: 201 - 534
POSITION\tREPEAT\t\t\t\tSPACER
--------\t-----------------------------\t--------------------------------
201\t\tCGGTTTATCCCCGCTGATGCGGGGAACAC\tCAGCGTCAGGCGTGAAATCTCACCGTCGTTGC\t[ 29, 32 ]
262\t\tCGGTTTATCCCTGCTGGCGCGGGGAACTC\tTCGGTTCAGGCGTTGCAAACCTGGCTACCGGG\t[ 29, 32 ]
323\t\tCGGTTTATCCCCGCTAACGCGGGGAACTC\tGTAGTCCATCATTCCACCTATGTCTGAACTCC\t[ 29, 32 ]
384\t\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\tCCGGGGGATAATGTTTACGGTCATGCGCCCCC\t[ 29, 32 ]
445\t\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\tTGGGCGGCTTGCCTTGCAGCCAGCTCCAGCAG\t[ 29, 32 ]
506\t\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\t
"""

FAKE = '''
import pathlib, sys
out = pathlib.Path(sys.argv[-1])
out.write_text("""Sequence 'x' (562 bp)

CRISPR 1   Range: 201 - 534
POSITION\\tREPEAT\\t\\t\\t\\tSPACER
--------\\t-----------------------------\\t--------------------------------
201\\t\\tCGGTTTATCCCCGCTGATGCGGGGAACAC\\tCAGCGTCAGGCGTGAAATCTCACCGTCGTTGC\\t[ 29, 32 ]
262\\t\\tCGGTTTATCCCTGCTGGCGCGGGGAACTC\\tTCGGTTCAGGCGTTGCAAACCTGGCTACCGGG\\t[ 29, 32 ]
323\\t\\tCGGTTTATCCCCGCTAACGCGGGGAACTC\\tGTAGTCCATCATTCCACCTATGTCTGAACTCC\\t[ 29, 32 ]
384\\t\\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\\tCCGGGGGATAATGTTTACGGTCATGCGCCCCC\\t[ 29, 32 ]
445\\t\\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\\tTGGGCGGCTTGCCTTGCAGCCAGCTCCAGCAG\\t[ 29, 32 ]
506\\t\\tCGGTTTATCCCCGCTGGCGCGGGGAACTC\\t
""")
'''


def test_parse_crisprs() -> None:
    arrays = parse_crisprs(SAMPLE, ["NC_000913.3_crispr1"])
    assert len(arrays) == 1
    array = arrays[0]
    assert array["start"] == 201
    assert array["end"] == 534
    assert array["length"] == 334
    assert array["n_repeats"] == 6
    assert array["repeat_length"] == 29
    assert array["spacer_length"] == 32
    assert array["consensus_repeat"] == "CGGTTTATCCCCGCTGGCGCGGGGAACTC"
    assert array["positions"][-1] == 506


def test_parse_empty() -> None:
    assert parse_crisprs("", ["x"]) == []


def test_run_with_fake_binary(tmp_path) -> None:
    binary = tmp_path / "minced.py"
    binary.write_text(FAKE, encoding="utf-8")
    form = encode_sequences(["ACGT" * 50], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["genome"] = form
    run(
        ctx,
        [
            {
                "name": "crispr_array_detect",
                "inputs": ["genome"],
                "params": {"minced_path": str(binary), "output": "arrays"},
            }
        ],
    )
    out = ctx["arrays"]
    assert out.dims == ["array", "statistic"]
    assert out.data.shape == (1, 6)
    assert out.info["n_arrays"] == 1
    assert out.info["arrays"][0]["n_repeats"] == 6
    assert out.labels["array"] == {"array=1": 0}


def test_run_errors(tmp_path) -> None:
    form = encode_sequences(["ACGT" * 10], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["genome"] = form
    with pytest.raises(StepError, match="was not found"):
        run(
            ctx,
            [
                {
                    "name": "crispr_array_detect",
                    "inputs": ["genome"],
                    "params": {"minced_path": str(tmp_path / "missing")},
                }
            ],
        )


@pytest.mark.skipif(not MINCED, reason="minced is not available")
@pytest.mark.skipif(
    not os.environ.get("OPERON_REAL_CRISPR"), reason="set OPERON_REAL_CRISPR=1"
)
def test_real_minced(tmp_path) -> None:
    text = (FIXTURES / "ecoli_crispr.fa").read_text()
    sequence = "".join(line.strip() for line in text.splitlines() if not line.startswith(">"))
    form = encode_sequences([sequence], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["genome"] = form
    run(
        ctx,
        [
            {
                "name": "crispr_array_detect",
                "inputs": ["genome"],
                "params": {"minced_path": MINCED, "output": "arrays"},
            }
        ],
    )
    out = ctx["arrays"]
    assert out.info["n_arrays"] == 1
    array = out.info["arrays"][0]
    assert array["start"] == 201
    assert array["end"] == 534
    assert array["n_repeats"] == 6
    assert array["repeat_length"] == 29
