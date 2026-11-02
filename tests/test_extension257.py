"""Tests for the paratope prediction operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.antibody_cdr_kabat import TEMPLATE, kabat_regions
from src.task.step.steps.structure_paratope_predict import (
    paratope_rows,
    residue_cdr_map,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"


def _form():
    return read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def test_cdr_map_covers_the_three_loops() -> None:
    mapping = residue_cdr_map(TEMPLATE)
    expected = set()
    for name, start, end, _residues in kabat_regions(TEMPLATE):
        if name.startswith("CDR"):
            expected.update(range(start, end + 1))
    assert set(mapping) == expected
    assert {value[0] for value in mapping.values()} == {"CDR1", "CDR2", "CDR3"}


def test_paratope_rows_aggregate_atoms() -> None:
    labels = np.array(["A:ALA:1", "A:ALA:1", "A:GLY:2"], dtype=object)
    positions = {"A:ALA:1": 1, "A:GLY:2": 2}
    chains = {"A:ALA:1": "A", "A:GLY:2": "A"}
    cdrs = {"A": {1: ("CDR1", 2)}}
    counts = np.array([3, 2, 1], dtype=np.int64)
    distances = np.array([4.0, 5.0, 6.0], dtype=np.float64)
    rows = paratope_rows(labels, positions, chains, cdrs, counts, distances)
    assert [row["residue"] for row in rows] == ["A:ALA:1", "A:GLY:2"]
    first = rows[0]
    assert first["n_contacts"] == 5
    assert first["min_distance"] == pytest.approx(4.0)
    assert first["is_paratope"] == 1
    assert first["cdr"] == "CDR1"
    assert rows[1]["is_paratope"] == 0
    assert rows[1]["cdr"] == "framework"


def test_min_contacts_filters_residues() -> None:
    labels = np.array(["A:ALA:1", "A:GLY:2"], dtype=object)
    rows = paratope_rows(
        labels,
        {"A:ALA:1": 1, "A:GLY:2": 2},
        {"A:ALA:1": "A", "A:GLY:2": "A"},
        {"A": {}},
        np.array([3, 0]),
        np.array([4.0, np.inf]),
        min_contacts=2,
    )
    assert [row["residue"] for row in rows] == ["A:ALA:1"]


def test_run_finds_paratope_on_the_vhh_fixture(tmp_path) -> None:
    form = _form()
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    ctx.step_params = {
        "binder_chains": "A",
        "target_chains": "L",
        "cutoff": 5.0,
        "output": "paratope",
    }
    run(
        ctx,
        [
            {
                "name": "structure_paratope_predict",
                "inputs": ["pdb"],
                "params": {
                    "binder_chains": "A",
                    "target_chains": "L",
                    "cutoff": 5.0,
                    "output": "paratope",
                },
            }
        ],
    )
    out = ctx["paratope"]
    assert out.data.shape[0] > 0
    assert out.data.shape[1] == 4
    assert out.info["n_interface"] == out.data.shape[0]
    assert out.info["n_paratope"] > 0
    assert all(label.startswith("A:") for label in out.labels["residue"])
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["L"]


def test_validation_errors(tmp_path) -> None:
    form = _form()
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises((StepError, ValueError), match="cutoff"):
        run(
            ctx,
            [
                {
                    "name": "structure_paratope_predict",
                    "inputs": ["pdb"],
                    "params": {"binder_chains": "A", "target_chains": "L", "cutoff": 20.0},
                }
            ],
        )
    distant = Context(str(tmp_path / "distant"), {"params": {}})
    distant["pdb"] = _form()
    with pytest.raises(StepError, match="no binder residue contacts the target"):
        run(
            distant,
            [
                {
                    "name": "structure_paratope_predict",
                    "inputs": ["pdb"],
                    "params": {
                        "binder_chains": "A",
                        "target_chains": "B",
                        "cutoff": 3.0,
                        "output": "paratope",
                    },
                }
            ],
        )
