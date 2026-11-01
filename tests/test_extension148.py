"""Runner-level contract checks for the v1.27.0 operators."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from src.reader import pick_reader, read_source
from src.task.context.base import Context
from src.task.runner import run

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
sys.path.insert(0, str(Path(__file__).parent))
from test_extension147 import VHH_1MEL, _form  # noqa: E402


def _structure_form():
    return read_source(
        FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _context(tmp_path: Path) -> Context:
    return Context(tmp_path / "task", {"params": {}})


def test_sasa_runs_through_runner(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx["structure"] = _structure_form()
    run(
        ctx,
        [
            {
                "name": "sasa_per_residue",
                "inputs": ["structure"],
                "params": {"output": "sasa"},
            }
        ],
    )
    out = ctx["sasa"]
    assert out.data.shape == (16, 3)
    assert out.info["n_residues"] == 16
    export = json.loads(
        (ctx.out_dir / "steps" / "01_sasa_per_residue.json").read_text(encoding="utf-8")
    )
    assert export["n_residues"] == 16


def test_cdr_motifs_runs_through_runner(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx["sequence"] = _form([VHH_1MEL])
    run(
        ctx,
        [
            {
                "name": "antibody_cdr_motifs",
                "inputs": ["sequence"],
                "params": {"output": "liabilities"},
            }
        ],
    )
    out = ctx["liabilities"]
    assert out.data.shape == (3, 7)
    assert list(out.labels["region"]) == ["CDR1", "CDR2", "CDR3"]


def test_rdkit_triage_runs_through_runner(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    run(
        ctx,
        [
            {"name": "rdkit_qed", "inputs": [], "params": {"smiles": "CCO ethanol", "output": "qed"}},
            {
                "name": "rdkit_oral_bioavailability",
                "inputs": [],
                "params": {"smiles": "CCO ethanol", "output": "bio"},
            },
        ],
    )
    assert ctx["qed"].data.shape == (1, 8)
    assert ctx["bio"].data.shape == (1, 11)
    assert ctx["bio"].data[0, 10] == 1.0
