"""Tests for structure_halogen_bond_scan."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_halogen_bond_scan import (
    StructureHalogenBondScanStep,
    atom_table,
    halogen_bonds,
    halogen_donors,
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


# carbon at the origin, iodine 2.1 A along +x, an oxygen 3.9 A along +x: C-X...O ~ 180 deg.
BOND_ROWS = [
    (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
    (2.1, 0.0, 0.0, 1, "LIG", "A", "I1", "I"),
    (4.0, 0.0, 0.0, 2, "LIG", "A", "O1", "O"),
]


def test_atom_table_decodes_columns() -> None:
    table = atom_table(_form(BOND_ROWS), "field")
    assert table["elements"].tolist() == ["C", "I", "O"]
    assert table["labels"][0] == "A:LIG:1:C1"
    assert table["coords"][1].tolist() == pytest.approx([2.1, 0.0, 0.0])


def test_donors_and_bonds() -> None:
    table = atom_table(_form(BOND_ROWS), "field")
    donors = halogen_donors(table)
    assert len(donors) == 1
    assert donors[0]["label"] == "A:LIG:1:I1"
    bonds = halogen_bonds(table)
    assert len(bonds) == 1
    bond = bonds[0]
    assert bond["donor"] == "A:LIG:1:I1"
    assert bond["acceptor"] == "A:LIG:2:O1"
    assert bond["distance"] == pytest.approx(1.9, abs=1e-6)
    assert bond["angle_deg"] == pytest.approx(180.0, abs=1e-4)


def test_bond_filters_distance_and_angle() -> None:
    table = atom_table(_form(BOND_ROWS), "field")
    assert halogen_bonds(table, max_distance=1.5) == []
    bent = atom_table(
        _form(
            [
                (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
                (2.1, 0.0, 0.0, 1, "LIG", "A", "I1", "I"),
                (3.1, 1.732, 0.0, 2, "LIG", "A", "O1", "O"),
            ]
        ),
        "field",
    )
    assert halogen_bonds(bent) == []
    assert len(halogen_bonds(bent, min_angle=110.0)) == 1
    perpendicular = atom_table(
        _form(
            [
                (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
                (2.1, 0.0, 0.0, 1, "LIG", "A", "I1", "I"),
                (2.1, 3.0, 0.0, 2, "LIG", "A", "O1", "O"),
            ]
        ),
        "field",
    )
    assert halogen_bonds(perpendicular) == []


def test_step_output_and_export() -> None:
    step = StructureHalogenBondScanStep()
    ctx = Ctx({"output": "hb"})
    step.run(ctx, [_form(BOND_ROWS)])
    out = ctx["hb"]
    assert list(out.dims) == ["bond", "statistic"]
    assert out.data.shape == (1, 2)
    assert out.data[0, 0] == pytest.approx(1.9, abs=1e-6)
    assert out.info["n_bonds"] == 1
    export = step.export(ctx)
    assert export["n_bonds"] == 1
    assert export["mean_angle_deg"] == pytest.approx(180.0, abs=1e-4)


def test_parameter_and_input_errors() -> None:
    form = _form(BOND_ROWS)
    step = StructureHalogenBondScanStep()
    with pytest.raises(StepError, match="a PDB form input is required"):
        step.run(Ctx({}), [])
    with pytest.raises(StepError, match="max_distance"):
        step.run(Ctx({"max_distance": 9.0}), [form])
    with pytest.raises(StepError, match="min_angle"):
        step.run(Ctx({"min_angle": 45.0}), [form])
    with pytest.raises(StepError, match="bond_length"):
        step.run(Ctx({"bond_length": 0.5}), [form])
    with pytest.raises(StepError, match="no halogen atoms"):
        step.run(Ctx({}), [_form([(0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C")])])
    far = _form(
        [
            (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
            (2.1, 0.0, 0.0, 1, "LIG", "A", "I1", "I"),
            (12.0, 0.0, 0.0, 2, "LIG", "A", "O1", "O"),
        ]
    )
    with pytest.raises(StepError, match="no halogen bond"):
        step.run(Ctx({}), [far])
