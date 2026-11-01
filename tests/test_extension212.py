"""Tests for the ligand steric clash operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.interface_bsa import vdw_radii
from src.task.step.steps.structure_ligand_clash import (
    StructureLigandClashStep,
    atom_table,
    clash_rows,
    heavy_mask,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows: list[tuple]) -> Form:
    text = {
        "resname": [row[3] for row in rows],
        "chain": [row[4] for row in rows],
        "atom_name": [row[6] for row in rows],
        "element": [row[7] for row in rows],
    }
    encoders = {}
    encoded = {}
    for name, values in text.items():
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(values)
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            np.asarray([row[0] for row in rows], dtype=float),
            np.asarray([row[1] for row in rows], dtype=float),
            np.asarray([row[2] for row in rows], dtype=float),
            np.asarray([float(row[5]) for row in rows]),
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


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params: dict, form: Form):
    ctx = Ctx(params)
    step = StructureLigandClashStep()
    step.run(ctx, [form])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx), ctx


def _row(x, y, z, resname, number, atom, element):
    return (x, y, z, resname, "A", number, atom, element)


def test_hand_clash_counts() -> None:
    rows = [
        _row(0.0, 0.0, 0.0, "ALA", 1, "CA", "C"),
        _row(10.0, 0.0, 0.0, "ALA", 2, "CA", "C"),
        _row(1.0, 0.0, 0.0, "LIG", 101, "C1", "C"),
        _row(9.9, 0.0, 0.0, "LIG", 101, "C2", "C"),
    ]
    form = _pdb_form(rows)
    out, export, _ = _run({"tolerance": 0.4}, form)
    assert out.data.shape == (2, 3)
    assert out.labels["ligand_atom"] == {"A:LIG:101:C1": 0, "A:LIG:101:C2": 1}
    # C1: distance 1.0, overlap 3.4-1.0 = 2.4 > 0.4 -> clash; nearest 1.0
    assert float(out.data[0, 0]) == 1.0
    assert float(out.data[0, 1]) == pytest.approx(2.4, rel=1e-5)
    assert float(out.data[0, 2]) == pytest.approx(1.0, rel=1e-5)
    # C2: nearest protein atom is 0.1 away -> overlap 3.3 and one clash
    assert float(out.data[1, 0]) == 1.0
    assert float(out.data[1, 2]) == pytest.approx(0.1, rel=1e-5)
    assert export["n_ligand_atoms"] == 2
    assert export["n_clashes"] == 2


def test_oracle_agrees() -> None:
    rows = [
        _row(0.0, 0.0, 0.0, "ALA", 1, "CA", "C"),
        _row(3.0, 0.0, 0.0, "ALA", 2, "CA", "C"),
        _row(1.5, 0.0, 0.0, "LIG", 101, "C1", "C"),
    ]
    form = _pdb_form(rows)
    table = atom_table(form, "atom", "field")
    heavy = heavy_mask(table["element"])
    radii = vdw_radii(table["element"])
    ligand = heavy & (table["resname"] == "LIG")
    protein = heavy & (table["resname"] == "ALA")
    oracle, total = clash_rows(
        table["coords"][ligand], radii[ligand], table["coords"][protein], radii[protein], tolerance=0.4
    )
    out, _, _ = _run({"tolerance": 0.4}, form)
    np.testing.assert_allclose(out.data, np.asarray(oracle, dtype=np.float32), rtol=1e-5)
    assert int(out.info["n_clashes"]) == total == 2


def test_tolerance_and_scale_filters() -> None:
    rows = [_row(0.0, 0.0, 0.0, "ALA", 1, "CA", "C"), _row(3.2, 0.0, 0.0, "LIG", 101, "C1", "C")]
    form = _pdb_form(rows)
    strict, _, _ = _run({"tolerance": 0.4}, form)
    assert float(strict.data[0, 0]) == 0.0
    relaxed, _, _ = _run({"tolerance": 0.3, "clash_scale": 1.1}, form)
    assert float(relaxed.data[0, 0]) == 1.0


def test_parameter_and_input_errors() -> None:
    form = _pdb_form([_row(0.0, 0.0, 0.0, "ALA", 1, "CA", "C"), _row(0.5, 0.0, 0.0, "LIG", 101, "C1", "C")])
    for params, match in (
        ({"tolerance": -1.0}, "tolerance must be between"),
        ({"clash_scale": 2.0}, "clash_scale must be between"),
        ({"ligand_resnames": ""}, "ligand_resnames must name"),
        ({"ligand_resnames": "XYZ"}, "no ligand heavy atom matches"),
    ):
        with pytest.raises(StepError, match=match):
            _run(params, form)
    no_protein = _pdb_form([_row(0.0, 0.0, 0.0, "LIG", 101, "C1", "C")])
    with pytest.raises(StepError, match="no protein heavy atoms"):
        _run({"ligand_resnames": "LIG"}, no_protein)
    with pytest.raises(StepError, match="PDB form with dims"):
        _run({}, Form(data=np.zeros((1, 2), dtype=np.float32), dims=["atom", "feature"], labels={"atom": {"a": 0}, "feature": {"x": 0, "y": 1}}, info={}))
