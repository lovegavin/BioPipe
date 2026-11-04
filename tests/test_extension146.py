"""Tests for the per-residue SASA operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import pick_reader, read_source
from src.task.step.steps.sasa_per_residue import (
    SasaPerResidueStep,
    residue_sasa,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.written_outputs = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.written_outputs.add(key)


def _structure_form() -> Form:
    reader = pick_reader(FIXTURE).implementation()
    assert reader.definition["id"] == "PdbReader"
    return read_source(
        FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _run(params, form=None):
    step = SasaPerResidueStep()
    ctx = Ctx(params)
    step.run(ctx, [form if form is not None else _structure_form()])
    return ctx[params.get("output", "out")], step.export(ctx)


def test_single_sphere_matches_analytic_area() -> None:
    coords = np.zeros((1, 3))
    radii = np.array([1.7])
    residues = residue_sasa(coords, radii, np.array(["A:ALA:1"]), n_points=256)
    assert len(residues) == 1
    label, area, count = residues[0]
    assert label == "A:ALA:1"
    assert count == 1
    expected = 4.0 * np.pi * (1.7 + 1.4) ** 2
    assert area == pytest.approx(expected, rel=0.01)


def test_two_atoms_reduce_surface() -> None:
    coords = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    radii = np.array([1.7, 1.7])
    labels = np.array(["A:ALA:1", "A:ALA:1"])
    residues = residue_sasa(coords, radii, labels, n_points=256)
    assert len(residues) == 1
    _, together, count = residues[0]
    assert count == 2
    single = 4.0 * np.pi * (1.7 + 1.4) ** 2
    assert 0.6 * single < together < 1.9 * single


def test_fixture_total_matches_biopython() -> None:
    bio = pytest.importorskip("Bio.PDB.SASA")
    from Bio.PDB import PDBParser

    out, exported = _run({"output": "sasa"})
    assert out.dims == ["residue", "statistic"]
    assert out.data.shape == (16, 3)
    assert list(out.labels["residue"])[0] == "C:SER:60"
    assert out.data[0, 0] == pytest.approx(104.74, abs=0.05)
    assert out.data[0, 2] == 4.0
    assert out.info["n_residues"] == 16
    assert out.info["unit"] == "A^2"
    assert np.sum(out.data[:, 1]) == pytest.approx(1.0, abs=1e-5)

    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("fixture", str(FIXTURE))
    calculator = bio.ShrakeRupley(n_points=92)
    calculator.compute(structure, level="R")
    reference = {
        f"C:{residue.get_resname()}:{residue.get_id()[1]}": residue.sasa
        for residue in structure[0]["C"]
    }
    total = sum(reference.values())
    assert out.info["total_sasa"] == pytest.approx(total, rel=0.01)
    for index, label in enumerate(out.labels["residue"]):
        expected = reference[label]
        assert out.data[index, 0] == pytest.approx(expected, rel=0.25)
    assert exported["total_sasa"] == pytest.approx(total, rel=0.01)


def test_exclusions_and_custom_dimensions() -> None:
    step = SasaPerResidueStep()
    ctx = Ctx(
        {
            "output": "sasa",
            "residue_dim": "block",
            "probe_radius": 1.4,
            "n_points": 128,
            "exclude_resnames": "",
        }
    )
    step.run(ctx, [_structure_form()])
    out = ctx["sasa"]
    assert out.dims == ["block", "statistic"]
    assert out.data.shape == (16, 3)


def test_parameter_and_input_errors() -> None:
    form = _structure_form()
    with pytest.raises(StepError, match="probe_radius must be between"):
        _run({"probe_radius": 0.5}, form)
    with pytest.raises(StepError, match="n_points must be between"):
        _run({"n_points": 8}, form)
    with pytest.raises(StepError, match="is required, got"):
        _run({"atom_dim": "other"}, form)
    with pytest.raises(StepError, match="has no 'resname' column"):
        _run({}, Form(data=np.zeros((2, 3), np.float32), dims=["atom", "field"]))


def test_no_heavy_atoms() -> None:
    from src.reader.readers._encoder import LabelEncoder

    fields = ["element", "x", "y", "z", "residue_number", "chain", "atom_name", "resname"]
    encoder = LabelEncoder()
    encoded = encoder.fit_transform(["H", "H"])
    data = np.zeros((2, len(fields)), dtype=np.float32)
    data[:, fields.index("element")] = encoded
    data[:, fields.index("x")] = [0.0, 1.0]
    data[:, fields.index("residue_number")] = 1.0
    form = Form(
        data=data,
        dims=["atom", "field"],
        labels={
            "atom": {"0": 0, "1": 1},
            "field": {name: index for index, name in enumerate(fields)},
        },
        info={"encoders": {"field": {"element": encoder}}},
    )
    with pytest.raises(StepError, match="no heavy atoms"):
        _run({}, form)
