"""Runner-level contract checks for the v1.28.0 operators."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
CHECKPOINT = os.environ.get("BIOPIPE_ESM_IF_CHECKPOINT", "/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")


def _ctx(tmp_path):
    return Context(tmp_path / "task", {"params": {}})


def test_runner_accepts_sa_and_complexity(tmp_path):
    ctx = _ctx(tmp_path)
    ctx["sequence"] = encode_sequences(["ACDEFGHIKLMNPQRSTVWY", "AAAAAAAAGGGGGGGG"], "sequence", "position", "protein")
    run(
        ctx,
        [
            {"name": "rdkit_sa_score", "inputs": [], "params": {"smiles": "CCO ethanol\nc1ccccc1 ring", "output": "sa"}},
            {"name": "sequence_complexity", "inputs": ["sequence"], "params": {"output": "complexity"}},
        ],
    )
    assert ctx["sa"].data.shape == (2, 1)
    assert ctx["complexity"].data.shape == (2, 7)
    export = ctx.out_dir / "steps" / "02_sequence_complexity.json"
    assert export.is_file()


def test_runner_accepts_bfactor_profile(tmp_path):
    ctx = _ctx(tmp_path)
    ctx["structure"] = read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    run(
        ctx,
        [
            {"name": "structure_bfactor_profile", "inputs": ["structure"], "params": {"output": "profile"}},
        ],
    )
    assert ctx["profile"].data.shape == (16, 3)
    assert ctx["profile"].info["n_residues"] == 16


def test_runner_accepts_esm_if_redesign(tmp_path):
    if not Path(CHECKPOINT).is_file():
        pytest.skip("ESM-IF checkpoint is not available")
    pytest.importorskip("biotite")
    try:
        pytest.importorskip("torch_scatter")
    except OSError as exc:
        pytest.skip(f"torch_scatter is ABI-incompatible: {exc}")
    ctx = _ctx(tmp_path)
    ctx["structure"] = read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    run(
        ctx,
        [
            {
                "name": "esm_if_redesign",
                "inputs": ["structure"],
                "params": {
                    "chain": "C",
                    "model_path": CHECKPOINT,
                    "design_positions": "1",
                    "num_samples": 1,
                    "temperature": 0.1,
                    "seed": 1,
                },
            }
        ],
    )
    out = ctx["output"]
    assert out.data.shape == (1, 3)
    assert out.info["design_positions"] == [1]
