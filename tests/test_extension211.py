"""Tests for the helix-helix geometry operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_helix_helix_angle import (
    StructureHelixHelixAngleStep,
    ca_atoms,
    helix_axis,
    helix_runs,
    line_distance,
    pair_rows,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows: list[tuple]) -> Form:
    """rows: (x, y, z, resname, chain, number, atom_name, element)."""
    text_values = {
        "resname": [row[3] for row in rows],
        "chain": [row[4] for row in rows],
        "atom_name": [row[6] for row in rows],
        "element": [row[7] for row in rows],
    }
    numbers = [row[5] for row in rows]
    xyz = [[row[0], row[1], row[2]] for row in rows]
    encoders = {}
    encoded = {}
    for name, values in text_values.items():
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(values)
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            np.asarray([value[0] for value in xyz]),
            np.asarray([value[1] for value in xyz]),
            np.asarray([value[2] for value in xyz]),
            np.asarray([float(value) for value in numbers]),
            encoded["resname"],
            encoded["chain"],
            encoded["atom_name"],
            encoded["element"],
        ]
    ).astype(np.float32)
    dims = ["atom", "field"]
    labels = {
        "atom": {f"atom:{index}": index for index in range(len(rows))},
        "field": {name: index for index, name in enumerate(COLUMNS)},
    }
    return Form(
        data=matrix,
        dims=dims,
        labels=labels,
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _helix(chain: str, first: int, count: int, *, origin=(0.0, 0.0, 0.0), axis="z") -> list[tuple]:
    rows = []
    for index in range(count):
        angle = np.radians(100.0 * index)
        radius = 2.3
        along = 1.5 * index
        if axis == "z":
            x, y, z = radius * np.cos(angle), radius * np.sin(angle), along
        else:
            x, y, z = along, radius * np.cos(angle), radius * np.sin(angle)
        rows.append(
            (
                origin[0] + x,
                origin[1] + y,
                origin[2] + z,
                "ALA",
                chain,
                first + index,
                "CA",
                "C",
            )
        )
    return rows


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params: dict, form: Form):
    ctx = Ctx(params)
    step = StructureHelixHelixAngleStep()
    step.run(ctx, [form])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx), ctx


def test_helix_runs_and_axis() -> None:
    rows = _helix("A", 1, 10)
    form = _pdb_form(rows)
    labels, ca = ca_atoms(form, "atom", "field")
    assert len(ca) == 10
    runs = helix_runs(ca)
    assert runs == [list(range(10))]
    centre, axis, span = helix_axis(ca)
    assert abs(abs(axis[2]) - 1.0) < 1e-2
    assert span > 13.0


def test_pair_geometry_parallel_and_perpendicular() -> None:
    first = _helix("A", 1, 10, origin=(0, 0, 0))
    second = _helix("B", 1, 10, origin=(10, 0, 0))
    rows = first + second
    form = _pdb_form(rows)
    out, export, _ = _run({"cutoff": 4.0}, form)
    assert out.data.shape == (1, 6)
    assert out.labels["helix_pair"] == {"helix1-helix2": 0}
    assert float(out.data[0, 0]) == pytest.approx(0.0, abs=1e-3)
    assert float(out.data[0, 1]) == pytest.approx(10.0, rel=0.02)
    assert float(out.data[0, 2]) == pytest.approx(6.35, rel=0.05)
    assert export["n_helices"] == 2
    assert float(out.data[0, 3]) == pytest.approx(0.0)

    # a permissive cutoff must find close CA pairs between the two helices
    loose, _, _ = _run({"cutoff": 8.0}, form)
    assert float(loose.data[0, 3]) > 0

    # perpendicular helices: rotate the second one onto the x axis
    third = _helix("C", 1, 10, origin=(0, 20, 0), axis="x")
    out2, _, _ = _run({"cutoff": 12.0}, _pdb_form(first + third))
    assert float(out2.data[0, 0]) == pytest.approx(90.0, abs=8.0)


def test_line_distance_helper() -> None:
    assert line_distance(np.zeros(3), np.array([0, 0, 1.0]), np.array([3, 4, 0]), np.array([0, 0, 1.0])) == pytest.approx(5.0)
    assert line_distance(np.zeros(3), np.array([0, 0, 1.0]), np.array([0, 5, 0]), np.array([1.0, 0, 0])) == pytest.approx(5.0)


def test_pair_rows_contacts() -> None:
    first = _helix("A", 1, 10)
    second = _helix("B", 1, 10, origin=(6, 0, 0))
    form = _pdb_form(first + second)
    labels, ca = ca_atoms(form, "atom", "field")
    runs = helix_runs(ca)
    rows = pair_rows(ca, labels, runs, cutoff=12.0)
    assert rows[0][3] > 0


def test_parameter_and_input_errors() -> None:
    form = _pdb_form(_helix("A", 1, 10) + _helix("B", 1, 10, origin=(10, 0, 0)))
    for params, match in (
        ({"cutoff": 1.0}, "cutoff must be between"),
        ({"min_residues": 2}, "min_residues must be at least 3"),
    ):
        with pytest.raises(StepError, match=match):
            _run(params, form)
    single = _pdb_form(_helix("A", 1, 10))
    with pytest.raises(StepError, match="at least two helices"):
        _run({}, single)
    with pytest.raises(StepError, match="PDB form with dims"):
        _run({}, Form(data=np.zeros((2, 2), dtype=np.float32), dims=["atom", "feature"], labels={"atom": {"a": 0, "b": 1}, "feature": {"x": 0, "y": 1}}, info={}))
    short = _pdb_form([(0.0, 0.0, float(index), "ALA", "A", index + 1, "CA", "C") for index in range(3)])
    with pytest.raises(StepError, match="at least four CA atoms"):
        _run({}, short)
