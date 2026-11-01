"""Tests for the ligand residue contact map operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_ligand_residue_map import (
    StructureLigandResidueMapStep,
    contact_matrix,
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


def _fixture() -> Form:
    return _form(
        [
            (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
            (2.0, 0.0, 0.0, 1, "LIG", "A", "C2", "C"),
            (0.0, 0.0, 3.0, 1, "ALA", "A", "CA", "C"),
            (0.0, 0.0, 6.0, 2, "GLY", "A", "CA", "C"),
            (0.0, 0.0, 2.0, 3, "HOH", "W", "O", "O"),
        ]
    )


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "contact_map", **params}
        self.metadata = {}


def _run(params, form, *, output="contact_map"):
    step = StructureLigandResidueMapStep()
    ctx = Ctx({**params, "output": output})
    step.run(ctx, [form])
    return ctx[output], step.export(ctx)


def test_contact_matrix_helper() -> None:
    matrix, rows, columns = contact_matrix(
        np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]]),
        np.array(["lig1", "lig2"]),
        np.array([[0.0, 0.0, 3.0], [0.0, 0.0, 6.0]]),
        ["A:ALA1", "A:GLY2"],
        cutoff=4.0,
        value="count",
    )
    assert matrix.tolist() == [[1.0, 0.0], [1.0, 0.0]]
    assert rows.tolist() == ["lig1", "lig2"]
    assert columns == ["A:ALA1", "A:GLY2"]


def test_step_counts_and_distances() -> None:
    out, export = _run({"cutoff": 4.5}, _fixture())
    assert out.data.shape == (2, 2)
    assert out.labels["ligand_atom"] == {"A:LIG1:C1": 0, "A:LIG1:C2": 1}
    assert list(out.labels["residue"]) == ["A:ALA1", "A:GLY2"]
    assert out.data.tolist() == [[1.0, 0.0], [1.0, 0.0]]
    assert out.info["n_contacts"] == 2
    assert export["n_residues"] == 2

    distances, _ = _run({"cutoff": 4.5, "value": "min_distance"}, _fixture())
    assert distances.data[0, 0] == pytest.approx(3.0)
    assert np.isnan(distances.data[0, 1])


def test_water_is_excluded_and_can_be_included() -> None:
    out, _ = _run({"cutoff": 3.0}, _fixture())
    assert "W:HOH3" not in out.labels["residue"]
    included, _ = _run({"cutoff": 3.0, "exclude_resnames": ""}, _fixture())
    assert "W:HOH3" in included.labels["residue"]


def test_parameter_errors() -> None:
    form = _fixture()
    with pytest.raises(StepError, match="cutoff"):
        _run({"cutoff": 0.5}, form)
    with pytest.raises(StepError, match="value"):
        _run({"value": "mean"}, form)
    with pytest.raises(StepError, match="must differ"):
        _run({"ligand_dim": "residue"}, form)
    with pytest.raises(StepError, match="no ligand atom"):
        _run({"ligand_resnames": "XYZ"}, form)
