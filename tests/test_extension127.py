"""Interface hotspot operator (v1.23.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps.interface_bsa import InterfaceBsaStep, sasa_per_atom, vdw_radii
from src.task.step.steps.interface_hotspots import InterfaceHotspotsStep


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
    return PdbReader().read(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def _run(params, form):
    ctx = Ctx({"binder_chains": "A", **params})
    step = InterfaceHotspotsStep()
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


_CONTACT_ATOMS = [
    _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 3.0),
    _atom(2, "CA", "GLY", "A", 2, 3.0, 0.0, 0.0),
    _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 4.0),
    _atom(4, "CA", "THR", "B", 2, 0.0, 0.0, 6.0),
]


def _coordinates(form, column: str):
    index = form.labels["field"][column]
    return np.asarray(form.data[:, index], dtype=np.float64)


def _brute_force_contacts(form, binder, target, cutoff):
    chain = form.info["encoders"]["field"]["chain"].inverse_transform(
        form.data[:, form.labels["field"]["chain"]]
    )
    residue = form.info["encoders"]["field"]["resname"].inverse_transform(
        form.data[:, form.labels["field"]["resname"]]
    )
    number = form.data[:, form.labels["field"]["residue_number"]]
    coords = np.column_stack([_coordinates(form, axis) for axis in ("x", "y", "z")])
    binder_mask = np.isin(chain, binder)
    target_mask = np.isin(chain, target)
    counts: dict[str, int] = {}
    for index in np.flatnonzero(binder_mask):
        label = f"{chain[index]}:{residue[index]}:{int(round(number[index]))}"
        distance = np.linalg.norm(coords[target_mask] - coords[index], axis=1)
        counts[label] = counts.get(label, 0) + int((distance <= cutoff).sum())
    for index in np.flatnonzero(target_mask):
        label = f"{chain[index]}:{residue[index]}:{int(round(number[index]))}"
        distance = np.linalg.norm(coords[binder_mask] - coords[index], axis=1)
        counts[label] = counts.get(label, 0) + int((distance <= cutoff).sum())
    return counts


def test_contact_counts_match_brute_force(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, export = _run({"cutoff": 5.0}, form)
    expected = _brute_force_contacts(form, ["A"], ["B"], 5.0)
    labels = list(out.labels["residue"])
    assert set(labels) == set(expected)
    for label in labels:
        assert float(out.data[out.labels["residue"][label], 0]) == pytest.approx(expected[label])
    assert export["hotspots"] == 4
    assert list(out.labels["statistic"]) == ["contact_count", "min_distance", "buried_area"]


def test_contacts_and_distances(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, _export = _run({"cutoff": 5.0}, form)
    row = out.labels["residue"]
    contacts = np.asarray(out.data[:, 0])
    distances = np.asarray(out.data[:, 1])
    assert contacts[row["A:ALA:1"]] == 2
    assert distances[row["A:ALA:1"]] == pytest.approx(1.0, abs=1e-6)
    assert contacts[row["A:GLY:2"]] == 1
    assert distances[row["A:GLY:2"]] == pytest.approx(5.0, abs=1e-6)
    assert contacts[row["B:SER:1"]] == 2
    assert contacts[row["B:THR:2"]] == 1


def test_default_sorting_is_by_contacts_then_buried(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, _export = _run({"cutoff": 5.0}, form)
    contacts = np.asarray(out.data[:, 0])
    assert list(contacts) == sorted(contacts, reverse=True)
    assert list(out.labels["residue"])[:2] == ["A:ALA:1", "B:SER:1"]


def test_sort_by_buried_area(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, export = _run({"cutoff": 5.0, "sort_by": "buried"}, form)
    buried = np.asarray(out.data[:, 2])
    assert list(buried) == sorted(buried.tolist(), reverse=True)
    assert export["total_buried_area"] > 0.0
    assert export["hotspots"] == 4


def test_buried_area_matches_interface_bsa(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    _out, export = _run({"cutoff": 5.0}, form)

    ctx = Ctx({"binder_chains": "A"})
    bsa = InterfaceBsaStep()
    bsa.run(ctx, [form])
    interfaces = ctx["out"].info
    assert export["total_buried_area"] == pytest.approx(
        interfaces["total_buried_area"], abs=1e-3
    )
    assert 2 <= interfaces["interface_residues"] <= 4


def test_min_contacts_filters_rows(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, export = _run({"cutoff": 5.0, "min_contacts": 2}, form)
    assert set(out.labels["residue"]) == {"A:ALA:1", "B:SER:1"}
    assert export["hotspots"] == 2


def test_excluded_water_does_not_count_as_contacts(tmp_path):
    atoms = list(_CONTACT_ATOMS) + [
        _atom(5, "O", "HOH", "W", 1, 0.0, 0.0, 3.5, "O", record="HETATM")
    ]
    form = _pdb_form(tmp_path, atoms)
    out, export = _run({"cutoff": 5.0}, form)
    assert "W:HOH:1" not in out.labels["residue"]
    assert out.labels["residue"]["A:ALA:1"] == 0
    assert export["hotspots"] == 4


def test_target_chain_is_derived(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, export = _run({"cutoff": 5.0, "binder_chains": "A"}, form)
    assert export["target_chains"] == ["B"]
    assert set(out.labels["residue"]) == {"A:ALA:1", "A:GLY:2", "B:SER:1", "B:THR:2"}


def test_parameter_and_input_errors(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    with pytest.raises(StepError, match="cutoff must be positive"):
        _run({"cutoff": 0.0}, form)
    with pytest.raises(StepError, match="min_contacts must be at least one"):
        _run({"cutoff": 5.0, "min_contacts": 0}, form)
    with pytest.raises(StepError, match="probe_radius must be between"):
        _run({"cutoff": 5.0, "probe_radius": 5.0}, form)
    with pytest.raises(StepError, match="n_points must be between"):
        _run({"cutoff": 5.0, "n_points": 4}, form)
    with pytest.raises(StepError, match="sort_by must be"):
        _run({"cutoff": 5.0, "sort_by": "energy"}, form)
    with pytest.raises(StepError, match="binder_chains or target_chains"):
        _run({"cutoff": 5.0, "binder_chains": "", "target_chains": ""}, form)
    with pytest.raises(StepError, match="not found in the PDB form"):
        _run({"cutoff": 5.0, "binder_chains": "Z"}, form)
    with pytest.raises(StepError, match="cannot be both binder and target"):
        _run({"cutoff": 5.0, "binder_chains": "A", "target_chains": "A"}, form)
    hydrogen = [_atom(1, "H", "ALA", "A", 1, 0.0, 0.0, 0.0, "H")]
    with pytest.raises(StepError, match="no heavy atoms left"):
        _run({"cutoff": 5.0}, _pdb_form(tmp_path, hydrogen, "h.pdb"))
    from src.core import Form

    wrong = Form(
        data=np.zeros((2, 3), dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {"a": 0, "b": 1}, "feature": {"f": 0, "g": 1, "h": 2}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="expected a \\[atom, field\\]"):
        _run({"cutoff": 5.0}, wrong)


def test_export_and_labels(tmp_path):
    form = _pdb_form(tmp_path, _CONTACT_ATOMS)
    out, export = _run({"cutoff": 5.0, "binder_chains": "A", "target_chains": "B"}, form)
    assert export["binder_chains"] == ["A"]
    assert export["target_chains"] == ["B"]
    assert out.info["cutoff"] == 5.0
    assert out.info["min_contacts"] == 1
    assert out.info["n_points"] == 92
    assert out.info["unit"] == "A^2"
