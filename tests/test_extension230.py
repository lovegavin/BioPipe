"""Tests for the cavity lining operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._protein_common import residue_order
from src.task.step.steps.structure_cavity_lining import (
    StructureCavityLiningStep,
    cavity_cells,
    lining_rows,
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


def test_lining_rows_hand_counted() -> None:
    residue_coords = {"A:1": np.array([[0.0, 0.0, 0.0]]), "A:2": np.array([[10.0, 0.0, 0.0]])}
    centres = np.array([[0.0, 0.0, 0.0]])
    assert lining_rows(residue_coords, centres, cutoff=4.0) == [("A:1", 0.0, 1)]
    rows = lining_rows(residue_coords, centres, cutoff=12.0)
    assert [row[0] for row in rows] == ["A:1", "A:2"]
    assert rows[1][1] == pytest.approx(10.0)


def test_cavity_cells_hand_counted() -> None:
    from src.task.step.steps._protein_common import decode_column

    form = _hollow_cube()
    coords = np.column_stack(
        [
            decode_column(form, "field", name).astype(float)
            for name in ("x", "y", "z")
        ]
    )
    radii = np.full(len(coords), 1.7)
    components, centres, shape, lo = cavity_cells(
        coords, radii, spacing=1.0, probe_radius=1.4, padding=2.0
    )
    assert components, "an enclosed hollow cube must leave a buried cavity"
    volumes = sorted((len(cells) * 1.0 for cells in components), reverse=True)
    assert volumes[0] == pytest.approx(27.0)
    assert centres.shape[0] == int(np.prod(shape))
    assert lo.shape == (3,)


def test_runner_round_trip_lining(tmp_path) -> None:
    ctx = Context(str(tmp_path / "lining"), {"params": {}})
    ctx["pdb"] = _hollow_cube()
    run(
        ctx,
        [
            {
                "name": "structure_cavity_lining",
                "inputs": ["pdb"],
                "params": {"min_volume": 5.0, "lining_cutoff": 12.0, "output": "lining"},
            }
        ],
    )
    form = ctx["lining"]
    assert form.dims == ["residue", "statistic"]
    assert form.data.shape[0] >= 1
    distances = form.data[:, 0]
    assert np.all(distances <= 12.0)
    assert np.all(np.diff(distances) >= -1e-6)
    labels = [label for label, _ in sorted(form.labels["residue"].items(), key=lambda item: item[1])]
    assert all(label.startswith("A:") for label in labels)
    assert form.info["cavity_volume"] > 0.0
    assert ctx.step_params["output"] == "lining"
    assert set(residue_order(form.labels["residue"])) == set(labels)


def test_validation_errors(tmp_path) -> None:
    step = StructureCavityLiningStep()
    assert step.definition["inputs_arity"] == 1
    components, _, _, _ = cavity_cells(
        np.array([[0.0, 0.0, 0.0]]), np.array([1.7]), spacing=1.0, probe_radius=1.4, padding=1.0
    )
    assert components == []

    ctx = Context(str(tmp_path / "errors"), {"params": {}})
    ctx["pdb"] = _pdb_form([(0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C")])
    with pytest.raises(StepError, match="no buried cavity"):
        run(
            ctx,
            [
                {
                    "name": "structure_cavity_lining",
                    "inputs": ["pdb"],
                    "params": {"output": "lining"},
                }
            ],
        )
