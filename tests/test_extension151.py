"""Extension tests for the structure B-factor profile operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import read_source
from src.task.step.steps.structure_bfactor_profile import (
    StructureBfactorProfileStep,
    numeric_column,
    residue_profile,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(path=FIXTURE, dims=("atom", "field")):
    return read_source(path, dims=list(dims), labels={"atom": "auto", "field": "builtin"})


def _run(params, form=None):
    step = StructureBfactorProfileStep()
    ctx = Ctx(params)
    step.run(ctx, [form if form is not None else _form()])
    return ctx["out"], step.export(ctx)


def _atom_line(serial, name, resname, chain, number, x, y, z, bfactor, element):
    return (
        "ATOM  %5d %-4s %3s %1s%4d    %8.3f%8.3f%8.3f%6.2f%6.2f          %2s"
        % (serial, name, resname, chain, number, x, y, z, 1.0, bfactor, element)
    )


def _write_pdb(tmp_path, lines):
    path = tmp_path / "bfactor.pdb"
    path.write_text("HEADER    TEST\n" + "\n".join(lines) + "\nEND\n", encoding="utf-8")
    return path


def test_fixture_profile_matches_recomputed_bfactors():
    out, export = _run({})
    form = _form()
    bfactor = numeric_column(form, "field", "bfactor")
    assert out.data.shape == (16, 3)
    np.testing.assert_allclose(out.info["global_mean"], float(np.mean(bfactor)), rtol=1e-6)
    assert out.info["n_residues"] == 16
    assert list(out.labels["statistic"]) == ["mean_bfactor", "max_bfactor", "n_atoms"]
    assert out.labels["residue"]["C:VAL:75"] == 0
    assert export["most_flexible"][0] == "C:VAL:75"


def test_order_is_descending_by_mean_bfactor():
    out, _ = _run({})
    means = out.data[:, 0]
    assert all(means[index] >= means[index + 1] for index in range(len(means) - 1))


def test_water_is_excluded(tmp_path):
    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, 10.0, "C"),
        _atom_line(2, "CA", "GLY", "A", 2, 3.8, 0.0, 0.0, 30.0, "C"),
    ]
    water = "HETATM    3  O   HOH A 101       0.000   4.000   0.000  1.00 99.00           O"
    path = _write_pdb(tmp_path, lines + [water])
    out, _ = _run({}, form=_form(path))
    assert out.info["n_residues"] == 2
    assert "A:HOH:101" not in out.labels["residue"]
    assert out.info["global_mean"] == pytest.approx(20.0, abs=1e-4)


def test_included_water_when_exclude_list_is_empty(tmp_path):
    lines = [_atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, 10.0, "C")]
    water = "HETATM    2  O   HOH A 101       0.000   4.000   0.000  1.00 40.00           O"
    path = _write_pdb(tmp_path, lines + [water])
    out, _ = _run({"exclude_resnames": ""}, form=_form(path))
    assert out.info["n_residues"] == 2
    assert out.labels["residue"]["A:HOH:101"] == 0


def test_parameter_errors():
    with pytest.raises(StepError, match="structure form with dims"):
        _run({}, form=_form(dims=("atom", "feature")))
    form = _form()
    form.labels["field"] = {key: value for key, value in form.labels["field"].items() if key != "bfactor"}
    with pytest.raises(StepError, match="has no 'bfactor' column"):
        _run({}, form=form)


def test_residue_profile_helper_skips_hydrogens():
    form = _form()
    rows = residue_profile(form, "field", set())
    assert len(rows) == 16
    assert all(row[3] >= 1 for row in rows)
