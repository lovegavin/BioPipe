"""Runner-level contract checks for the v1.24.0 operators.

The unit tests call ``step.run`` directly. This module drives the same
operators through ``src.task.runner.run`` so the declared output contracts are
validated exactly as a saved workflow would validate them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import test_extension132 as design_tests
import test_extension133 as score_tests
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


def _pdb_form():
    return read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def _context(tmp_path, name):
    return Context(tmp_path / name, {"params": {}})


def test_structure_hbonds_contract(tmp_path):
    ctx = _context(tmp_path, "hbonds")
    ctx["pdb"] = _pdb_form()
    run(ctx, [{"name": "structure_hbonds", "inputs": ["pdb"], "params": {"output": "hbonds"}}])
    result = ctx["hbonds"]
    assert list(result.dims) == ["residue", "statistic"]
    assert int(result.info["n_bonds"]) == 10


def test_structure_contacts_contract(tmp_path):
    ctx = _context(tmp_path, "contacts")
    ctx["pdb"] = _pdb_form()
    run(
        ctx,
        [
            {
                "name": "structure_contacts",
                "inputs": ["pdb"],
                "params": {"output": "contacts", "include_intra": True},
            }
        ],
    )
    result = ctx["contacts"]
    assert list(result.dims) == ["residue", "statistic"]
    assert result.data.shape[1] == 2


def test_rdkit_mcs_contract(tmp_path):
    ctx = _context(tmp_path, "mcs")
    run(
        ctx,
        [
            {
                "name": "rdkit_mcs",
                "params": {"output": "mcs", "smiles": "c1ccccc1 benzene\nCc1ccccc1 toluene"},
            }
        ],
    )
    result = ctx["mcs"]
    assert int(result.info["mcs_num_atoms"]) == 6
    assert float(result.data[0, 0]) >= 6


def test_ligandmpnn_design_contract(tmp_path):
    repo, weights = design_tests._repo(tmp_path)
    ctx = _context(tmp_path, "design")
    run(
        ctx,
        [
            {
                "name": "ligandmpnn_design",
                "params": {
                    "output": "designs",
                    "structure_path": str(FIXTURE),
                    "ligandmpnn_path": str(repo),
                    "weights_path": str(weights),
                    "python_executable": sys.executable,
                    "seed": 7,
                },
            }
        ],
    )
    result = ctx["designs"]
    assert list(result.dims) == ["design", "statistic"]
    assert result.data.shape == (2, 3)


def test_ligandmpnn_score_contract(tmp_path):
    repo, weights = score_tests._repo(tmp_path)
    ctx = _context(tmp_path, "score")
    run(
        ctx,
        [
            {
                "name": "ligandmpnn_score",
                "params": {
                    "output": "scores",
                    "structure_path": str(FIXTURE),
                    "ligandmpnn_path": str(repo),
                    "weights_path": str(weights),
                    "python_executable": sys.executable,
                },
            }
        ],
    )
    result = ctx["scores"]
    assert list(result.dims) == ["residue", "statistic"]
    assert result.data.shape[1] == 2
