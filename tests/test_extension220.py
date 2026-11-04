"""Tests for the buried cavity scan operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_cavity_scan import (
    StructureCavityScanStep,
    cavity_components,
    cavity_rows,
    free_mask,
    grid_shape,
    outside_mask,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [numerics[0], numerics[1], numerics[2], numerics[3],
         encoded["resname"], encoded["chain"], encoded["atom_name"], encoded["element"]]
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
    return _form(rows)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "cavities", **params}
        self.metadata = {}


def _run(params, form, *, output="cavities"):
    step = StructureCavityScanStep()
    ctx = Ctx({**params, "output": output})
    step.run(ctx, [form])
    return ctx[output], step.export(ctx)


def test_grid_helpers() -> None:
    lo = np.array([0.0, 0.0, 0.0])
    hi = np.array([4.0, 4.0, 4.0])
    assert grid_shape(lo, hi, 1.0) == (5, 5, 5)
    assert grid_shape(lo, hi, 2.0) == (3, 3, 3)


def test_free_and_outside_masks() -> None:
    coords = np.zeros((1, 3))
    radii = np.array([1.7])
    centres = np.array([[10.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    mask = free_mask(centres, (2, 1, 1), coords, radii, 1.4)
    assert mask.tolist() == [True, False]

    shape = (3, 3, 3)
    free = np.zeros(shape, dtype=bool)
    free[1, 1, 1] = True
    reachable = outside_mask(free, shape)
    assert not reachable[1, 1, 1]
    open_free = np.ones(shape, dtype=bool)
    assert outside_mask(open_free, shape).all()


def test_hollow_cube_has_one_cavity() -> None:
    form = _hollow_cube()
    out, export = _run({"spacing": 1.0, "probe_radius": 1.4, "min_volume": 5.0}, form)
    assert out.data.shape[1] == 5
    assert export["n_cavities"] >= 1
    assert list(out.labels["statistic"]) == ["volume", "n_cells", "centroid_x", "centroid_y", "centroid_z"]
    volume_column = out.data[:, 0]
    assert float(volume_column.max()) > 5.0
    centre = out.data[0, 2:5]
    assert np.abs(centre).max() < 2.5


def test_open_structure_has_no_cavity() -> None:
    form = _form(
        [
            (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
            (30.0, 0.0, 0.0, 2, "ALA", "A", "CA", "C"),
            (0.0, 30.0, 0.0, 3, "ALA", "A", "CA", "C"),
        ]
    )
    out, export = _run({"min_volume": 1.0}, form)
    assert out.data.shape == (0, 5)
    assert export["n_cavities"] == 0


def test_cavity_components_helper() -> None:
    cavity = np.zeros((3, 3, 3), dtype=bool)
    cavity[1, 1, 1] = True
    cavity[0, 0, 0] = True
    components = cavity_components(cavity, (3, 3, 3))
    assert sorted(len(part) for part in components) == [1, 1]
    rows = cavity_rows(components, np.zeros(3), 1.0, (3, 3, 3), 0.0)
    assert len(rows) == 2


def test_parameter_errors() -> None:
    form = _hollow_cube()
    with pytest.raises(StepError, match="dims"):
        _run({}, form, output="cavities") if False else _run({"atom_dim": "coords"}, form)
    with pytest.raises(StepError, match="spacing"):
        _run({"spacing": 0.1}, form)
    with pytest.raises(StepError, match="probe_radius"):
        _run({"probe_radius": 4.0}, form)
    with pytest.raises(StepError, match="min_volume"):
        _run({"min_volume": -1.0}, form)


def test_hydrogen_only_structure_rejected() -> None:
    form = _form([(0.0, 0.0, 0.0, 1, "ALA", "A", "H", "H")])
    with pytest.raises(StepError, match="no heavy atoms"):
        _run({}, form)
