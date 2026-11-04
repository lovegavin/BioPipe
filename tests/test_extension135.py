"""Tests for the interface contact map operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import pick_reader, read_source
from src.task.step.steps.interface_contact_map import (
    InterfaceContactMapStep,
    contact_pairs,
)


def _atom(record, serial, name, resname, chain, number, x, y, z, element):
    return (
        f"{record:<6}{serial:>5} {name:<4} {resname:>3} {chain:1}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{0.0:>6.2f}          {element:>2}"
    )


def _pdb_text() -> str:
    rows = [
        "HEADER    TEST PROTEIN",
        _atom("ATOM", 1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
        _atom("ATOM", 2, "CA", "ALA", "A", 2, 3.0, 0.0, 0.0, "C"),
        _atom("ATOM", 3, "CA", "ALA", "A", 3, 0.0, 0.0, 10.0, "C"),
        _atom("ATOM", 4, "CA", "SER", "B", 1, 0.0, 0.0, 4.0, "C"),
        _atom("ATOM", 5, "CA", "SER", "B", 2, 2.0, 0.0, 0.0, "C"),
        "END",
    ]
    return "\n".join(rows) + "\n"


@pytest.fixture()
def form(tmp_path):
    path = tmp_path / "complex.pdb"
    path.write_text(_pdb_text(), encoding="utf-8")
    reader = pick_reader(path).implementation()
    return read_source(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
        reader_id=reader.name,
    )


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(form, params):
    step = InterfaceContactMapStep()
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_binary_contact_map(form):
    out, export = _run(form, {"binder_chains": "A", "target_chains": "B", "cutoff": 4.5})
    assert list(out.dims) == ["binder_residue", "target_residue"]
    assert [label for label, index in sorted(out.labels["binder_residue"].items(), key=lambda item: item[1])] == [
        "A:ALA:1",
        "A:ALA:2",
        "A:ALA:3",
    ]
    assert [label for label, index in sorted(out.labels["target_residue"].items(), key=lambda item: item[1])] == [
        "B:SER:1",
        "B:SER:2",
    ]
    np.testing.assert_array_equal(out.data, np.array([[1, 1], [0, 1], [0, 0]], np.float32))


def test_min_distance_map(form):
    out, export = _run(
        form,
        {"binder_chains": "A", "target_chains": "B", "cutoff": 4.5, "value": "min_distance"},
    )
    expected = np.array([[4.0, 2.0], [np.nan, 1.0], [np.nan, np.nan]], np.float32)
    np.testing.assert_allclose(out.data, expected, rtol=1e-5, atol=1e-6, equal_nan=True)
    assert export["n_contacts"] == 3
    assert export["binder_coverage"] == pytest.approx(2 / 3, abs=1e-3)
    assert export["target_coverage"] == pytest.approx(1.0, abs=1e-3)


def test_brute_force_oracle(form):
    out, _ = _run(
        form,
        {"binder_chains": "A", "target_chains": "B", "cutoff": 10.0, "value": "min_distance"},
    )
    coords = {
        "A:ALA:1": (0.0, 0.0, 0.0),
        "A:ALA:2": (3.0, 0.0, 0.0),
        "A:ALA:3": (0.0, 0.0, 10.0),
        "B:SER:1": (0.0, 0.0, 4.0),
        "B:SER:2": (2.0, 0.0, 0.0),
    }
    for row, binder in enumerate(["A:ALA:1", "A:ALA:2", "A:ALA:3"]):
        for column, target in enumerate(["B:SER:1", "B:SER:2"]):
            expected = float(np.linalg.norm(np.subtract(coords[binder], coords[target])))
            if expected <= 10.0:
                assert out.data[row, column] == pytest.approx(expected, rel=1e-5, abs=1e-5)
            else:
                assert np.isnan(out.data[row, column])


def test_tighter_cutoff_drops_pairs(form):
    out, export = _run(form, {"binder_chains": "A", "target_chains": "B", "cutoff": 2.5})
    np.testing.assert_array_equal(out.data, np.array([[0, 1], [0, 1], [0, 0]], np.float32))
    assert export["n_contacts"] == 2


def test_derived_target_chain(form):
    out, export = _run(form, {"binder_chains": "A"})
    assert export["target_chains"] == ["B"]
    np.testing.assert_array_equal(out.data, np.array([[1, 1], [0, 1], [0, 0]], np.float32))


def test_contact_pairs_helper():
    best = contact_pairs(
        np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]]),
        np.array([0, 1]),
        np.array([[0.0, 0.0, 2.0]]),
        np.array([0]),
        4.5,
    )
    assert best == {(0, 0): 2.0, (1, 0): pytest.approx(3.6055, rel=1e-3)}


def test_parameter_errors(form):
    with pytest.raises(StepError, match="cutoff"):
        _run(form, {"cutoff": 0.0})
    with pytest.raises(StepError, match="value"):
        _run(form, {"value": "intensity"})
    with pytest.raises(StepError, match="must be different"):
        _run(form, {"binder_dim": "residue", "target_dim": "residue"})
    with pytest.raises(StepError, match="chain"):
        _run(form, {"binder_chains": "Z"})


def test_dims_error():
    form = Form(
        data=np.zeros((3, 3), np.float32),
        dims=["atom", "coordinate"],
        labels={"atom": {"a": 0, "b": 1, "c": 2}, "coordinate": {"x": 0, "y": 1, "z": 2}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="dims"):
        _run(form, {})
