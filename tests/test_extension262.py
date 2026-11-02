"""Tests for glycosylation sites."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences


def _pdb(path: Path, rows) -> Path:
    lines = []
    for serial, (resname, chain, number, atom_name, element, x, y, z) in enumerate(rows, start=1):
        lines.append(
            "ATOM  "
            f"{serial:5d} {atom_name:<4s} {resname:>3s} {chain}{number:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 50.00          {element:>2s}"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")
    return path

from src.task.step.steps.structure_glycosylation_sites import (
    residue_sasa,
    sequons,
)


def _form(path):
    return read_source(path, ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_sequons_hand_cases() -> None:
    assert sequons("NAT") == [(1, "NAT", "N-linked")]
    assert sequons("NAS") == [(1, "NAS", "N-linked")]
    assert sequons("NPT") == []
    assert sequons("nat") == [(1, "NAT", "N-linked")]
    assert sequons("NATNAT") == [(1, "NAT", "N-linked"), (4, "NAT", "N-linked")]
    assert sequons("AST", include_o_linked=True) == [
        (2, "S", "O-linked"),
        (3, "T", "O-linked"),
    ]


def test_residue_sasa_is_positive() -> None:
    path = _pdb(
        Path("/tmp") / "glyco_sasa.pdb",
        [
            ("ASN", "A", 1, "CA", "C", 0.0, 0.0, 0.0),
            ("ALA", "A", 2, "CA", "C", 3.8, 0.0, 0.0),
        ],
    )
    exposure = residue_sasa(_form(path), "atom", "field")
    assert set(exposure) == {"A:ASN:1", "A:ALA:2"}
    assert all(mean > 0 for mean, _count in exposure.values())


def test_run_reports_sequons(tmp_path) -> None:
    path = _pdb(
        tmp_path / "glyco.pdb",
        [
            ("ASN", "A", 1, "CA", "C", 0.0, 0.0, 0.0),
            ("ALA", "A", 2, "CA", "C", 3.8, 0.0, 0.0),
            ("THR", "A", 3, "CA", "C", 7.6, 0.0, 0.0),
            ("GLY", "A", 4, "CA", "C", 11.4, 0.0, 0.0),
            ("SER", "A", 5, "CA", "C", 15.2, 0.0, 0.0),
        ],
    )
    form = _form(path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    ctx.step_params = {"min_sasa": 0.0, "output": "sites"}
    run(
        ctx,
        [
            {
                "name": "structure_glycosylation_sites",
                "inputs": ["pdb"],
                "params": {"min_sasa": 0.0, "output": "sites"},
            }
        ],
    )
    out = ctx["sites"]
    assert out.data.shape == (1, 5)
    assert out.info["n_sites"] == 1
    assert out.info["n_exposed"] == 1
    assert out.info["motifs"] == ["NAT"]
    assert out.data[0, 0] == 1.0


def test_run_without_sequon_is_empty(tmp_path) -> None:
    path = _pdb(
        tmp_path / "plain.pdb",
        [("ALA", "A", 1, "CA", "C", 0.0, 0.0, 0.0)],
    )
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form(path)
    ctx.step_params = {"output": "sites"}
    run(
        ctx,
        [
            {
                "name": "structure_glycosylation_sites",
                "inputs": ["pdb"],
                "params": {"output": "sites"},
            }
        ],
    )
    assert ctx["sites"].data.shape == (0, 5)
    assert ctx["sites"].info["n_sites"] == 0


def test_validation_errors(tmp_path) -> None:
    path = _pdb(tmp_path / "plain.pdb", [("ALA", "A", 1, "CA", "C", 0.0, 0.0, 0.0)])
    form = _form(path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    ctx.step_params = {"output": "sites", "min_sasa": 5.0}
    with pytest.raises((StepError, ValueError), match="min_sasa"):
        run(
            ctx,
            [
                {
                    "name": "structure_glycosylation_sites",
                    "inputs": ["pdb"],
                    "params": {"output": "sites", "min_sasa": -1.0},
                }
            ],
        )
