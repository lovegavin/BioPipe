"""Tests for structure_missing_residues, structure_altloc_inventory and
structure_cis_peptides."""

from __future__ import annotations

import numpy as np
import pytest
from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_altloc_inventory import (
    StructureAltlocInventoryStep,
    altloc_rows,
)
from src.task.step.steps.structure_cis_peptides import (
    StructureCisPeptidesStep,
    cis_peptide_rows,
)
from src.task.step.steps.structure_missing_residues import (
    StructureMissingResiduesStep,
    missing_residue_rows,
)

FIELD_NAMES = (
    "x",
    "y",
    "z",
    "occupancy",
    "bfactor",
    "residue_number",
    "chain",
    "resname",
    "element",
    "atom_name",
    "altloc",
    "insertion_code",
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(atoms):
    columns = {
        "chain": [atom.get("chain", "A") for atom in atoms],
        "resname": [atom.get("resname", "ALA") for atom in atoms],
        "element": [atom.get("element", "C") for atom in atoms],
        "atom_name": [atom["atom_name"] for atom in atoms],
        "altloc": [atom.get("altloc", " ") for atom in atoms],
        "insertion_code": [" " for _ in atoms],
    }
    encoders = {name: LabelEncoder() for name in columns}
    codes = {name: encoders[name].fit_transform(values) for name, values in columns.items()}
    matrix = []
    for index, atom in enumerate(atoms):
        matrix.append(
            [
                atom["x"],
                atom["y"],
                atom["z"],
                atom.get("occupancy", 1.0),
                atom.get("bfactor", 0.0),
                atom["number"],
                codes["chain"][index],
                codes["resname"][index],
                codes["element"][index],
                codes["atom_name"][index],
                codes["altloc"][index],
                codes["insertion_code"][index],
            ]
        )
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom{i}": i for i in range(len(matrix))},
            "field": {name: position for position, name in enumerate(FIELD_NAMES)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _residue(number, chain="A", offset=(0.0, 0.0, 0.0), altloc=" "):
    x, y, z = offset
    return [
        {"atom_name": "N", "element": "N", "x": x - 1.2, "y": y, "z": z, "number": number,
         "chain": chain, "altloc": altloc},
        {"atom_name": "CA", "element": "C", "x": x, "y": y, "z": z, "number": number,
         "chain": chain, "altloc": altloc},
        {"atom_name": "C", "element": "C", "x": x + 1.5, "y": y, "z": z, "number": number,
         "chain": chain, "altloc": altloc},
    ]


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_missing_residues_reports_internal_gaps() -> None:
    atoms = _residue(1) + _residue(2) + _residue(5) + _residue(6)
    atoms += _residue(10, chain="B") + _residue(12, chain="B")
    out, info = _run(StructureMissingResiduesStep(), {}, _form(atoms))
    assert out.data.shape == (2, 3)
    assert set(out.labels["gap"]) == {"A:3-4", "B:11"}
    assert info["n_gaps"] == 2 and info["n_missing_total"] == 3
    np.testing.assert_allclose(out.data[0], [3, 4, 2])
    np.testing.assert_allclose(out.data[1], [11, 11, 1])


def test_missing_residues_empty_when_contiguous() -> None:
    atoms = _residue(1) + _residue(2) + _residue(3)
    out, info = _run(StructureMissingResiduesStep(), {}, _form(atoms))
    assert out.data.shape == (0, 3)
    assert out.labels["gap"] == {}
    assert info["n_gaps"] == 0


def test_missing_residues_ignores_waters() -> None:
    water = [
        {"atom_name": "O", "element": "O", "x": 0.0, "y": 0.0, "z": 0.0, "number": 2001,
         "chain": "A", "resname": "HOH"},
    ]
    out, info = _run(StructureMissingResiduesStep(), {}, _form(_residue(46) + water))
    assert out.data.shape == (0, 3)
    assert info["n_gaps"] == 0
    assert out.info["spans"]["A"] == {"n_residues": 1, "first": 46, "last": 46}


def test_missing_residues_chain_filter_errors() -> None:
    with pytest.raises(StepError, match="chain 'Z' not found"):
        _run(StructureMissingResiduesStep(), {"chain": "Z"}, _form(_residue(1)))


def test_altloc_inventory_counts_conformers() -> None:
    atoms = _residue(1, altloc="A") + _residue(1, altloc="B") + _residue(2)
    out, info = _run(StructureAltlocInventoryStep(), {}, _form(atoms))
    assert set(out.labels["altloc"]) == {"_", "A", "B"}
    rows = {label: out.data[index] for label, index in out.labels["altloc"].items()}
    np.testing.assert_allclose(rows["_"], [3, 1, 1.0, 1.0, 1.0])
    np.testing.assert_allclose(rows["A"], [3, 1, 1.0, 1.0, 1.0])
    assert info["n_altloc_atoms"] == 6
    assert info["n_residues_with_alternates"] == 1


def test_altloc_inventory_without_alternates() -> None:
    out, info = _run(StructureAltlocInventoryStep(), {}, _form(_residue(1) + _residue(2)))
    assert out.data.shape == (1, 5)
    assert info["n_altloc_atoms"] == 0
    assert out.data[0, 0] == 6


def _backbone(number, ca, c, n, chain="A"):
    return [
        {"atom_name": "N", "element": "N", "x": n[0], "y": n[1], "z": n[2], "number": number,
         "chain": chain},
        {"atom_name": "CA", "element": "C", "x": ca[0], "y": ca[1], "z": ca[2], "number": number,
         "chain": chain},
        {"atom_name": "C", "element": "C", "x": c[0], "y": c[1], "z": c[2], "number": number,
         "chain": chain},
    ]


def test_cis_peptide_detects_zero_omega() -> None:
    atoms = _backbone(1, (0, 0, 0), (1, 0, 0), (-1, 0, 0))
    atoms += _backbone(2, (0, 1, 0), (1, 1, 0), (1, 1, 0))
    atoms += _backbone(3, (2, 0, 0), (3, 0, 0), (1, 0, 0))
    out, info = _run(StructureCisPeptidesStep(), {}, _form(atoms))
    assert out.data.shape == (2, 3)
    np.testing.assert_allclose(out.data[0, 0], 0.0, atol=1e-4)
    assert out.data[0, 2] == 1.0
    np.testing.assert_allclose(abs(out.data[1, 0]), 180.0, atol=1e-3)
    assert out.data[1, 2] == 0.0
    assert info["n_cis"] == 1


def test_cis_peptides_skip_numbering_gaps() -> None:
    atoms = _backbone(1, (0, 0, 0), (1, 0, 0), (-1, 0, 0))
    atoms += _backbone(2, (0, 1, 0), (1, 1, 0), (1, 1, 0))
    atoms += _backbone(5, (2, 0, 0), (3, 0, 0), (1, 0, 0))
    out, info = _run(StructureCisPeptidesStep(), {}, _form(atoms))
    assert out.data.shape == (1, 3)
    assert info["n_bonds"] == 1 and info["n_skipped"] == 1


def test_cis_peptides_threshold_must_be_sane() -> None:
    with pytest.raises(StepError, match="between 0 and 90"):
        _run(StructureCisPeptidesStep(), {"cis_threshold": 120.0}, _form(_residue(1)))


def test_helpers_report_gaps_and_altlocs() -> None:
    residues = [
        {"chain": "A", "number": 1, "icode": "", "label": "A:1", "coords": {"CA": None}},
        {"chain": "A", "number": 3, "icode": "", "label": "A:3", "coords": {"CA": None}},
    ]
    rows, spans = missing_residue_rows(residues)
    assert rows[0]["label"] == "A:2" and spans["A"]["n_residues"] == 2
    form = _form(_residue(1, altloc="A") + _residue(1, altloc="B"))
    rows, summary = altloc_rows(form, "atom", "field")
    assert {row["altloc"] for row in rows} == {"A", "B"}
    assert summary["n_residues_with_alternates"] == 1
