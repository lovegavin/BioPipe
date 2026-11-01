"""Tests for structure_helix_bend."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_helix_bend import (
    StructureHelixBendStep,
    bend_row,
    direction_vectors,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(rows) -> Form:
    columns = list(zip(*rows))
    numeric = {
        "x": np.asarray(columns[0], dtype=np.float32),
        "y": np.asarray(columns[1], dtype=np.float32),
        "z": np.asarray(columns[2], dtype=np.float32),
        "residue_number": np.asarray(columns[3], dtype=np.float32),
    }
    text = {"resname": columns[4], "chain": columns[5], "atom_name": columns[6], "element": columns[7]}
    encoders = {}
    encoded = {}
    for name, values in text.items():
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(values))
        encoders[name] = encoder
    data = np.column_stack(
        [numeric["x"], numeric["y"], numeric["z"], numeric["residue_number"],
         encoded["resname"], encoded["chain"], encoded["atom_name"], encoded["element"]]
    ).astype(np.float32)
    return Form(
        data=data,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _helix(chain: str, origin=(0.0, 0.0, 0.0), count: int = 8, bend_deg: float = 0.0) -> list:
    rows = []
    direction = 0.0
    z = 0.0
    for index in range(count):
        angle = math.radians(100.0 * index)
        direction += math.radians(bend_deg)
        rows.append(
            (
                origin[0] + 2.3 * math.cos(angle) + z * math.sin(direction),
                origin[1] + 2.3 * math.sin(angle),
                origin[2] + z * math.cos(direction),
                index + 1,
                "ALA",
                chain,
                "CA",
                "C",
            )
        )
        z += 1.5
    return rows


def test_direction_vectors_and_bend_row() -> None:
    straight = np.array([[0.0, 0.0, 1.5 * index] for index in range(6)])
    directions = direction_vectors(straight, 4)
    assert len(directions) == 3
    assert directions[0].tolist() == pytest.approx([0.0, 0.0, 1.0])
    row = bend_row(straight, 4)
    assert row[0] == 6.0
    assert row[1] == pytest.approx(0.0, abs=1e-6)
    assert row[2] == pytest.approx(0.0, abs=1e-6)
    assert math.isinf(row[3])


def test_bend_row_curved_arc() -> None:
    radius = 20.0
    angles = np.linspace(0.0, math.radians(60.0), 9)
    points = np.column_stack([radius * np.cos(angles), radius * np.sin(angles), np.zeros_like(angles)])
    row = bend_row(points, 4)
    assert row[0] == 9.0
    assert row[1] > 20.0
    assert row[2] > 0.0
    assert row[3] == pytest.approx(radius, rel=0.35)


def test_step_straight_helix() -> None:
    form = _form(_helix("A", count=8))
    step = StructureHelixBendStep()
    ctx = Ctx({"output": "bends"})
    step.run(ctx, [form])
    out = ctx["bends"]
    assert list(out.dims) == ["helix", "statistic"]
    assert out.data.shape == (1, 4)
    assert out.data[0, 1] < 20.0
    assert out.data[0, 3] > 5.0
    assert out.info["n_helices"] == 1
    assert step.export(ctx)["n_helices"] == 1


def test_step_prefers_helices_only() -> None:
    form = _form(_helix("A", count=8) + _helix("B", origin=(20.0, 0.0, 0.0), count=8))
    step = StructureHelixBendStep()
    ctx = Ctx({"output": "bends"})
    step.run(ctx, [form])
    assert ctx["bends"].data.shape[0] == 2


def test_parameter_and_input_errors() -> None:
    form = _form(_helix("A", count=8))
    with pytest.raises(StepError, match="PDB form with dims"):
        StructureHelixBendStep().run(Ctx({}), [Form(data=form.data, dims=["atom", "feature"], labels={}, info={})])
    with pytest.raises(StepError, match="window must be an integer"):
        StructureHelixBendStep().run(Ctx({"window": 2}), [form])
    with pytest.raises(StepError, match="min_residues"):
        StructureHelixBendStep().run(Ctx({"min_residues": 2}), [form])
    with pytest.raises(StepError, match="a PDB form input is required"):
        StructureHelixBendStep().run(Ctx({}), [])


def test_no_helix_found() -> None:
    rows = [
        (float(index) * 9.0, 0.0, 0.0, index + 1, "ALA", "A", "CA", "C")
        for index in range(6)
    ]
    with pytest.raises(StepError, match="no helical run"):
        StructureHelixBendStep().run(Ctx({}), [_form(rows)])
