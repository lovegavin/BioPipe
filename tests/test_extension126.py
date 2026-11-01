"""Structure RMSD operator (v1.23.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps.structure_rmsd import StructureRmsdStep, kabsch, parse_fit_residues


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element="C", record="ATOM"):
    return (
        f"{record:<6}{serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{0.00:>6.2f}"
        f"          {element:>2}"
    )


def _pdb_form(tmp_path, atoms, name="x.pdb"):
    path = tmp_path / name
    path.write_text("\n".join(atoms) + "\nEND\n")
    reader = PdbReader()
    return reader.read(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def _run(params, *forms):
    ctx = Ctx(params)
    step = StructureRmsdStep()
    step.run(ctx, list(forms))
    return ctx["out"], step.export(ctx)


_BASE = [
    _atom(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
    _atom(2, "CA", "ALA", "A", 1, 1.2, 0.0, 0.0),
    _atom(3, "C", "ALA", "A", 1, 2.0, 1.0, 0.0),
    _atom(4, "CA", "GLY", "A", 2, 0.0, 2.5, 0.5),
    _atom(5, "N", "GLY", "A", 2, -0.5, 3.0, 1.0, "N"),
]


def _rigid(atoms, rotation, translation):
    return np.asarray([[float(atom[30:38]), float(atom[38:46]), float(atom[46:54])] for atom in atoms])


def _shifted(atoms, rotation, translation):
    coords = _rigid(atoms, rotation, translation)
    moved = (rotation @ coords.T).T + translation
    out = []
    for serial, (atom, point) in enumerate(zip(atoms, moved), start=1):
        out.append(
            atom[:30]
            + f"{point[0]:>8.3f}{point[1]:>8.3f}{point[2]:>8.3f}"
            + atom[54:]
        )
    return out


def test_kabsch_identity_and_translation():
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]])
    rotation, translation, rmsd = kabsch(points, points)
    np.testing.assert_allclose(rotation, np.eye(3), atol=1e-12)
    np.testing.assert_allclose(translation, np.zeros(3), atol=1e-12)
    assert rmsd == pytest.approx(0.0, abs=1e-12)

    moved = points + np.array([2.0, -1.0, 0.5])
    rotation, translation, rmsd = kabsch(points, moved)
    np.testing.assert_allclose(rotation, np.eye(3), atol=1e-12)
    np.testing.assert_allclose(translation, [2.0, -1.0, 0.5], atol=1e-12)
    assert rmsd == pytest.approx(0.0, abs=1e-12)


def test_identity_structure_has_zero_rmsd(tmp_path):
    form = _pdb_form(tmp_path, _BASE)
    out, export = _run({}, form, form)
    assert list(out.dims) == ["residue", "statistic"]
    assert list(out.labels["statistic"]) == ["rmsd", "n_atoms"]
    assert out.labels["residue"] == {"A:ALA:1": 0, "A:GLY:2": 1}
    np.testing.assert_allclose(out.data[:, 0], 0.0, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 1], [3.0, 2.0], atol=1e-6)
    assert export["rmsd"] == 0.0
    assert export["matched_atoms"] == 5


def test_rigid_motion_is_recovered_exactly(tmp_path):
    theta = np.pi / 2.0
    rotation = np.array(
        [[np.cos(theta), -np.sin(theta), 0.0], [np.sin(theta), np.cos(theta), 0.0], [0.0, 0.0, 1.0]]
    )
    reference = _pdb_form(tmp_path, _BASE, "reference.pdb")
    offset = np.array([1.0, 2.0, 3.0])
    mobile = _pdb_form(
        tmp_path,
        _shifted(_BASE, rotation.T, -(rotation.T @ offset)),
        "mobile.pdb",
    )
    out, export = _run({}, mobile, reference)
    assert export["rmsd"] == pytest.approx(0.0, abs=1e-3)
    np.testing.assert_allclose(out.data[:, 0], 0.0, atol=1e-3)
    np.testing.assert_allclose(np.asarray(out.info["rotation"]), rotation, atol=1e-3)
    np.testing.assert_allclose(np.asarray(out.info["translation"]), offset, atol=1e-3)


def test_biopython_superimposer_oracle(tmp_path):
    from Bio.SVDSuperimposer import SVDSuperimposer

    reference_atoms = _BASE
    perturbed = list(_BASE[:3]) + [_shifted([_BASE[3]], np.eye(3), np.array([0.0, 0.0, 0.6]))[0]] + [
        _BASE[4]
    ]
    mobile = _pdb_form(tmp_path, perturbed, "mobile.pdb")
    reference = _pdb_form(tmp_path, reference_atoms, "reference.pdb")
    out, export = _run({}, mobile, reference)

    mobile_coords = np.array(
        [[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in perturbed]
    )
    reference_coords = np.array(
        [[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in reference_atoms]
    )
    sup = SVDSuperimposer()
    sup.set(reference_coords, mobile_coords)
    sup.run()
    rotation, translation = sup.get_rotran()
    assert export["rmsd"] == pytest.approx(float(sup.get_rms()), abs=1e-5)
    np.testing.assert_allclose(np.asarray(out.info["rotation"]), rotation.T, atol=1e-5)
    np.testing.assert_allclose(np.asarray(out.info["translation"]), translation, atol=1e-5)


def test_per_residue_rmsd_reports_the_moved_residue(tmp_path):
    displaced = list(_BASE[:3]) + [
        _atom(4, "CA", "GLY", "A", 2, 0.0, 2.5, 3.5),
        _atom(5, "N", "GLY", "A", 2, -0.5, 3.0, 4.0, "N"),
    ]
    mobile = _pdb_form(tmp_path, _BASE, "mobile.pdb")
    reference = _pdb_form(tmp_path, displaced, "reference.pdb")
    out, _export = _run({}, mobile, reference)
    labels = out.labels["residue"]
    ala_rmsd = float(out.data[labels["A:ALA:1"], 0])
    gly_rmsd = float(out.data[labels["A:GLY:2"], 0])
    assert gly_rmsd > ala_rmsd
    assert gly_rmsd > 1.0


def test_fit_residues_restricts_the_superposition(tmp_path):
    displaced = list(_BASE[:3]) + [
        _atom(4, "CA", "GLY", "A", 2, 0.0, 2.5, 5.5),
        _atom(5, "N", "GLY", "A", 2, -0.5, 3.0, 6.0, "N"),
    ]
    mobile = _pdb_form(tmp_path, _BASE, "mobile.pdb")
    reference = _pdb_form(tmp_path, displaced, "reference.pdb")
    out, export = _run({"fit_residues": "A:1"}, mobile, reference)
    assert export["fit_atoms"] == 3
    assert export["rmsd"] == pytest.approx(0.0, abs=1e-3)
    assert float(out.data[out.labels["residue"]["A:GLY:2"], 0]) > 2.9


def test_atom_name_filter(tmp_path):
    mobile = _pdb_form(tmp_path, _BASE, "mobile.pdb")
    reference = _pdb_form(tmp_path, _BASE, "reference.pdb")
    _out, export = _run({"atom_names": "CA,N"}, mobile, reference)
    assert export["matched_atoms"] == 4
    assert export["fit_atoms"] == 4


def test_export_metadata(tmp_path):
    form = _pdb_form(tmp_path, _BASE)
    _out, export = _run({}, form, form)
    assert export["residues"] == 2
    assert export["mobile_chains"] == ["A"]
    assert export["reference_chains"] == ["A"]


def test_parameter_errors(tmp_path):
    form = _pdb_form(tmp_path, _BASE)
    with pytest.raises(StepError, match="min_rmsd"):
        _run({"min_rmsd": -1.0}, form, form)
    with pytest.raises(StepError, match="expected a \\[atom, field\\]"):
        _run({}, form, _sequence_form())
    with pytest.raises(StepError, match="at least three matched atoms"):
        _run({}, _pdb_form(tmp_path, _BASE[:2], "small.pdb"), form)
    with pytest.raises(StepError, match="no atoms are left"):
        _run({"atom_names": "ZZ"}, form, form)
    with pytest.raises(StepError, match="not of the form"):
        _run({"fit_residues": "A"}, form, form)
    with pytest.raises(StepError, match="starts after it ends"):
        _run({"fit_residues": "A:5-1"}, form, form)
    with pytest.raises(StepError, match="is not in the structure"):
        _run({"fit_residues": "Z:1-2"}, form, form)
    with pytest.raises(StepError, match="must cover at least three matched atoms"):
        _run({"fit_residues": "A:9-10"}, form, form)


def test_parse_fit_residues():
    spans = parse_fit_residues("A:1-5; B:7, B:9-10", {"A", "B"}, "structure_rmsd")
    assert spans == {"A": [(1, 5)], "B": [(7, 7), (9, 10)]}
    assert parse_fit_residues("", {"A"}, "structure_rmsd") == {}


def test_missing_atom_name_column(tmp_path):
    form = _pdb_form(tmp_path, _BASE)
    columns = ["x", "y", "z", "occupancy", "bfactor", "residue_number", "chain", "resname", "element"]
    stripped = Form(
        data=form.data[:, :9],
        dims=["atom", "field"],
        labels={
            "atom": dict(form.labels["atom"]),
            "field": {name: index for index, name in enumerate(columns)},
        },
        info=dict(form.info),
    )
    with pytest.raises(StepError, match="'atom_name' column"):
        _run({}, stripped, form)


def _sequence_form():
    from src.task.step.steps._sequence_common import encode_sequences

    return encode_sequences(["ACDE"], "sequence", "position", "protein")
