"""Tests for structure_chi_angles."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.structure_chi_angles import (
    CHI1,
    CHI2,
    StructureChiAnglesStep,
    chi_rows,
    dihedral,
    residue_atoms,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(rows, encoders=None):
    from src.reader.readers._encoder import LabelEncoder

    data = np.asarray([[row["x"], row["y"], row["z"]] for row in rows], dtype=np.float32)
    matrix = np.zeros((len(rows), 7), dtype=np.float32)
    matrix[:, 0:3] = data
    table = {
        "atom_name": [row["atom_name"] for row in rows],
        "chain": [row["chain"] for row in rows],
        "residue_number": [row["residue_number"] for row in rows],
        "resname": [row["resname"] for row in rows],
    }
    fitted = {}
    for column, (name, values) in enumerate(table.items(), start=3):
        encoder = LabelEncoder()
        matrix[:, column] = encoder.fit_transform(values)
        fitted[name] = encoder
    info = {"missing_code": np.nan, "encoders": {"field": encoders or fitted}}
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={"atom": {f"atom:{i}": i for i in range(len(rows))},
                "field": {"x": 0, "y": 1, "z": 2, "atom_name": 3, "chain": 4, "residue_number": 5, "resname": 6}},
        info=info,
        axis_info={},
    )


def _residue(name, atoms, chain="A", number=1):
    return [
        {"atom_name": atom, "chain": chain, "residue_number": str(number), "resname": name,
         "x": x, "y": y, "z": z}
        for atom, (x, y, z) in atoms.items()
    ]


def test_dihedral_matches_biopython() -> None:
    pytest.importorskip("Bio")
    from Bio.PDB.vectors import Vector, calc_dihedral

    points = [
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        np.array([1.0, 1.0, 0.0]),
        np.array([1.0, 1.0, 1.0]),
    ]
    expected = np.degrees(calc_dihedral(*[Vector(*point) for point in points]))
    assert dihedral(*points) == pytest.approx(expected, abs=1e-6)


def test_chi1_and_chi2_on_side_chain() -> None:
    atoms = {
        "N": (0.0, 0.0, 0.0),
        "CA": (1.0, 0.0, 0.0),
        "CB": (1.0, 1.0, 0.0),
        CHI1["SER"]: (1.0, 1.0, 1.0),
    }
    form = _form(_residue("SER", atoms))
    rows = chi_rows(form, "atom", "field")
    assert len(rows) == 1
    assert rows[0]["residue"] == "A:SER:1"
    assert rows[0]["values"]["chi1"] == pytest.approx(90.0, abs=1e-4)
    assert np.isnan(rows[0]["values"]["chi2"])


def test_chi2_on_lysine() -> None:
    pytest.importorskip("Bio")
    from Bio.PDB.vectors import Vector, calc_dihedral

    atoms = {
        "N": (0.0, 0.0, 0.0),
        "CA": (1.0, 0.0, 0.0),
        "CB": (1.0, 1.0, 0.0),
        "CG": (1.0, 1.0, 1.0),
        CHI2["LYS"]: (1.0, 2.0, 1.0),
    }
    form = _form(_residue("LYS", atoms))
    rows = chi_rows(form, "atom", "field")
    expected_chi2 = np.degrees(
        calc_dihedral(
            Vector(*atoms["CA"]),
            Vector(*atoms["CB"]),
            Vector(*atoms["CG"]),
            Vector(*atoms[CHI2["LYS"]]),
        )
    )
    assert rows[0]["values"]["chi1"] == pytest.approx(90.0, abs=1e-4)
    delta = (rows[0]["values"]["chi2"] - expected_chi2 + 180.0) % 360.0 - 180.0
    assert abs(delta) < 1e-4


def test_step_output() -> None:
    atoms = {"N": (0.0, 0.0, 0.0), "CA": (1.0, 0.0, 0.0), "CB": (1.0, 1.0, 0.0), "OG": (1.0, 1.0, 1.0)}
    form = _form(_residue("SER", atoms))
    ctx = Ctx({"output": "out"})
    step = StructureChiAnglesStep()
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (1, 3)
    assert list(out.labels["statistic"]) == ["chi1", "chi2", "chi3"]
    assert out.data[0, 0] == pytest.approx(90.0, abs=1e-4)
    assert np.isnan(out.data[0, 1]) and np.isnan(out.data[0, 2])
    assert out.info["n_chi1"] == 1 and out.info["n_chi2"] == 0
    assert step.export(ctx)["n_residues"] == 1


def test_parameter_and_input_errors() -> None:
    atoms = {"N": (0.0, 0.0, 0.0), "CA": (1.0, 0.0, 0.0), "CB": (1.0, 1.0, 0.0)}
    form = _form(_residue("SER", atoms))
    step = StructureChiAnglesStep()
    empty = form.__class__(
        data=np.zeros((0, 7), dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {}, "field": dict(form.labels["field"])},
        info={"missing_code": np.nan},
        axis_info={},
    )
    with pytest.raises(StepError, match="no residues"):
        step.run(Ctx({"output": "out"}), [empty])
    with pytest.raises(StepError, match="is required"):
        step.run(Ctx({"output": "out", "atom_dim": "other"}), [form])
    with pytest.raises(StepError, match="has no 'atom_name' column"):
        broken = form.__class__(
            data=form.data[:, 0:3], dims=["atom", "field"],
            labels={"atom": form.labels["atom"], "field": {"x": 0, "y": 1, "z": 2}},
            info={}, axis_info={})
        chi_rows(broken, "atom", "field")


def test_residue_atoms_groups() -> None:
    atoms = {"N": (0.0, 0.0, 0.0), "CA": (1.0, 0.0, 0.0), "CB": (1.0, 1.0, 0.0)}
    rows = _residue("SER", atoms) + _residue("GLY", atoms, number=2)
    form = _form(rows)
    order, groups = residue_atoms(form, "atom", "field")
    assert order == ["A:SER:1", "A:GLY:2"]
    assert set(groups["A:SER:1"]["atoms"]) == {"N", "CA", "CB"}
