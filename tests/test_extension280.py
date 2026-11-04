"""structure_dssp_segments: DSSP parsing and segments."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_dssp_segments import parse_dssp, segment_rows

TEXT = """  #  RESIDUE AA STRUCTURE BP1 BP2  ACC
    1    1 A M  -           0   0  100
    2    2 A K  E           0   0   90
    3    3 A L  E           0   0   80
    4    4 A V  H           0   0   70
    5    5 A A  H           0   0   60
"""


def test_parse_and_segments():
    records = parse_dssp(TEXT)
    assert [r["state"] for r in records] == ["coil", "strand", "strand", "helix", "helix"]
    segments = segment_rows(records)
    assert [(s["state"], s["start"], s["end"], s["length"]) for s in segments] == [
        ("coil", 1, 1, 1),
        ("strand", 2, 3, 2),
        ("helix", 4, 5, 2),
    ]


def test_run_on_fixture(tmp_path):
    binary = shutil.which("mkdssp")
    if binary is None:
        pytest.skip("mkdssp is not installed")
    fixture = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = __import__("src.reader", fromlist=["read_source"]).read_source(str(fixture), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    run(ctx, [{"name": "structure_dssp_segments", "inputs": ["pdb"], "params": {"output": "segments", "structure_path": str(fixture)}}])
    result = ctx["segments"]
    assert result.dims == ["segment", "statistic"]
    assert result.info["n_residues"] > 100
    assert abs(sum(result.info["fractions"].values()) - 1.0) < 1e-3


def test_errors():
    with pytest.raises(StepError, match="no residue"):
        segment_rows([])
    fixture = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
    from src.reader import read_source

    ctx = Context("/tmp/bp280", {"params": {}})
    ctx["pdb"] = read_source(str(fixture), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "structure_dssp_segments", "inputs": ["pdb"], "params": {"output": "s", "structure_path": "/nonexistent.pdb"}}])
