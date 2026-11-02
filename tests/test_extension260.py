"""Tests for the cavity druggability operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_cavity_druggability import (
    druggability_score,
    enclosure_fraction,
    hydrophobic_fraction,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            numerics[0],
            numerics[1],
            numerics[2],
            numerics[3],
            encoded["resname"],
            encoded["chain"],
            encoded["atom_name"],
            encoded["element"],
        ]
    ).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _hollow_cube(edge: float = 5.0, step: float = 1.5) -> Form:
    rows = []
    values = np.arange(-edge, edge + 1e-9, step)
    serial = 0
    for axis in range(3):
        for sign in (-1.0, 1.0):
            for first in values:
                for second in values:
                    coordinates = [0.0, 0.0, 0.0]
                    coordinates[axis] = sign * edge
                    coordinates[(axis + 1) % 3] = float(first)
                    coordinates[(axis + 2) % 3] = float(second)
                    serial += 1
                    rows.append((*coordinates, serial, "ALA", "A", "CA", "C"))
    return _pdb_form(rows)


def test_enclosure_fraction_hand_counted() -> None:
    assert enclosure_fraction([(0, 0, 0)]) == pytest.approx(1.0)
    cube = [(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    assert enclosure_fraction(cube) == pytest.approx(0.5)
    assert enclosure_fraction([]) == pytest.approx(0.0)


def test_hydrophobic_fraction_uses_kyte_doolittle() -> None:
    expected = ((3.8 + 4.5) / 9.0 + (4.2 + 4.5) / 9.0) / 2.0
    assert hydrophobic_fraction(["A:LEU:1", "A:VAL:2"]) == pytest.approx(expected)
    assert hydrophobic_fraction(["A:GLY:1"]) == pytest.approx(((-0.4) + 4.5) / 9.0)
    assert hydrophobic_fraction([]) == pytest.approx(0.0)


def test_druggability_score_is_bounded() -> None:
    assert druggability_score(0.5, 0.5) == pytest.approx(0.5)
    assert druggability_score(1.0, 1.0) == pytest.approx(1.0)
    assert druggability_score(0.0, 0.0) == pytest.approx(0.0)
    assert 0.0 <= druggability_score(2.0, -1.0) <= 1.0


def test_run_on_a_hollow_cube(tmp_path) -> None:
    form = _hollow_cube()
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    params = {
        "spacing": 1.0,
        "probe_radius": 1.4,
        "min_volume": 1.0,
        "padding": 2.0,
        "lining_cutoff": 4.0,
        "output": "druggability",
    }
    ctx.step_params = params
    run(ctx, [{"name": "structure_cavity_druggability", "inputs": ["pdb"], "params": params}])
    out = ctx["druggability"]
    assert out.data.shape == (1, 5)
    volume, n_lining, hydrophobicity, enclosure, score = out.data[0]
    assert volume > 10.0
    assert n_lining > 0
    assert 0.0 <= hydrophobicity <= 1.0
    assert 0.0 <= enclosure <= 1.0
    assert out.info["druggability"] == pytest.approx(float(score), rel=1e-6)
    assert out.info["n_lining"] > 0
    assert out.info["lining_residues"]


def test_open_structure_has_no_cavity(tmp_path) -> None:
    form = _pdb_form([(0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C")])
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="no buried cavity was found"):
        run(
            ctx,
            [
                {
                    "name": "structure_cavity_druggability",
                    "inputs": ["pdb"],
                    "params": {"spacing": 1.0, "min_volume": 1.0, "output": "druggability"},
                }
            ],
        )


def test_spacing_validation(tmp_path) -> None:
    form = _hollow_cube(edge=4.0, step=2.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises((StepError, ValueError), match="spacing"):
        run(
            ctx,
            [
                {
                    "name": "structure_cavity_druggability",
                    "inputs": ["pdb"],
                    "params": {"spacing": 9.0, "output": "druggability"},
                }
            ],
        )
