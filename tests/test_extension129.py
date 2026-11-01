"""Residue contact network operator (v1.24.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps.structure_contacts import StructureContactsStep, residue_graph


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


def _pdb_form(tmp_path, atoms, name="contacts.pdb"):
    path = tmp_path / name
    path.write_text("\n".join(atoms) + "\nEND\n")
    return PdbReader().read(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def _run(form, **params):
    step = StructureContactsStep()
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def _coords(form):
    return np.column_stack(
        [
            np.asarray(form.data[:, form.labels["field"][axis]], dtype=np.float64)
            for axis in ("x", "y", "z")
        ]
    )


def _labels(form):
    chain = form.info["encoders"]["field"]["chain"].inverse_transform(
        form.data[:, form.labels["field"]["chain"]]
    )
    resname = form.info["encoders"]["field"]["resname"].inverse_transform(
        form.data[:, form.labels["field"]["resname"]]
    )
    number = form.data[:, form.labels["field"]["residue_number"]]
    return [
        f"{chain[index]}:{resname[index]}:{int(round(number[index]))}"
        for index in range(len(chain))
    ]


# A1 (0,0,0), A2 (0,0,4), B1 (3,0,0), B2 (0,0,9)
_ATOMS = [
    _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
    _atom(2, "CA", "GLY", "A", 2, 0.0, 0.0, 4.0),
    _atom(3, "CA", "SER", "B", 1, 3.0, 0.0, 0.0),
    _atom(4, "CA", "THR", "B", 2, 0.0, 0.0, 9.0),
]


def test_cross_chain_contacts(tmp_path):
    form = _pdb_form(tmp_path, _ATOMS)
    out, export = _run(form, cutoff=4.5)
    labels = list(out.labels["residue"])
    assert labels == ["A:ALA:1", "B:SER:1"]  # both one contact, sorted by distance then label
    assert out.data.shape == (2, 2)
    assert out.labels["statistic"] == {"contact_count": 0, "min_distance": 1}
    np.testing.assert_allclose(out.data[:, 0], [1, 1])
    np.testing.assert_allclose(out.data[:, 1], [3.0, 3.0], rtol=1e-6)
    assert out.info["n_pairs"] == 1
    assert out.info["residue_pairs"] == [["A:ALA:1", "B:SER:1", 3.0]]
    assert out.info["chains"] == ["A", "B"]
    assert export["n_contact_residues"] == 2
    assert export["n_pairs"] == 1


def test_include_intra_adds_same_chain_contacts(tmp_path):
    form = _pdb_form(tmp_path, _ATOMS)
    out, _export = _run(form, cutoff=4.5, include_intra=True)
    labels = list(out.labels["residue"])
    assert labels == ["A:ALA:1", "B:SER:1", "A:GLY:2"]
    np.testing.assert_allclose(out.data[:, 0], [2, 1, 1])
    np.testing.assert_allclose(out.data[:, 1], [3.0, 3.0, 4.0], rtol=1e-6)
    assert out.info["n_pairs"] == 2


def test_min_distance_uses_closest_atom_pair(tmp_path):
    atoms = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CB", "ALA", "A", 1, 0.0, 0.0, 1.0),
        _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 4.5),
    ]
    form = _pdb_form(tmp_path, atoms)
    out, _export = _run(form, cutoff=4.5)
    labels = list(out.labels["residue"])
    assert labels == ["A:ALA:1", "B:SER:1"]
    np.testing.assert_allclose(out.data[:, 1], [3.5, 3.5], rtol=1e-6)


def test_min_contacts_filters_residues(tmp_path):
    form = _pdb_form(tmp_path, _ATOMS)
    out, export = _run(form, cutoff=4.5, include_intra=True, min_contacts=2)
    assert list(out.labels["residue"]) == ["A:ALA:1"]
    assert out.data.shape == (1, 2)
    assert export["n_rows"] == 1
    assert out.info["n_contact_residues"] == 3

    everything, everything_export = _run(form, cutoff=4.5, min_contacts=0)
    assert len(everything.labels["residue"]) == 4
    assert everything_export["n_rows"] == 4


def test_water_is_excluded_by_default(tmp_path):
    atoms = _ATOMS + [_atom(5, "O", "HOH", "W", 1, 0.0, 0.0, 0.5, element="O")]
    form = _pdb_form(tmp_path, atoms)
    out, _export = _run(form, cutoff=1.0)
    assert out.info["n_pairs"] == 0
    assert out.data.shape == (0, 2)

    kept, export = _run(form, cutoff=1.0, exclude_resnames="")
    assert export["n_pairs"] == 1
    assert kept.info["n_pairs"] == 1


def test_brute_force_oracle(tmp_path):
    rng = np.random.default_rng(7)
    atoms = []
    serial = 1
    for chain, count in (("A", 4), ("B", 5)):
        for residue in range(1, count + 1):
            for atom_name, offset in (("N", (0.0, 0.0, 0.0)), ("CA", (1.2, 0.3, 0.0))):
                x, y, z = rng.normal(scale=6.0, size=3) + np.asarray(offset)
                atoms.append(_atom(serial, atom_name, "ALA", chain, residue, x, y, z))
                serial += 1
    form = _pdb_form(tmp_path, atoms)
    cutoff = 5.0
    out, export = _run(form, cutoff=cutoff)

    coords = _coords(form)
    labels = _labels(form)
    unique = sorted(set(labels))
    chain_of = {label: label.split(":")[0] for label in unique}
    best: dict[tuple[str, str], float] = {}
    for first in range(len(coords)):
        for second in range(first + 1, len(coords)):
            if labels[first] == labels[second]:
                continue
            if chain_of[labels[first]] == chain_of[labels[second]]:
                continue
            distance = float(np.linalg.norm(coords[first] - coords[second]))
            if distance > cutoff:
                continue
            low, high = sorted((labels[first], labels[second]))
            key = (low, high)
            best[key] = min(best.get(key, distance), distance)
    expected_counts = {label: 0 for label in unique}
    expected_nearest = {label: np.inf for label in unique}
    for (low, high), distance in best.items():
        for label in (low, high):
            expected_counts[label] += 1
            expected_nearest[label] = min(expected_nearest[label], distance)

    rows = {label: (int(out.data[index, 0]), float(out.data[index, 1])) for index, label in enumerate(out.labels["residue"])}
    for label in unique:
        if expected_counts[label] == 0:
            assert label not in rows
            continue
        count, nearest = rows[label]
        assert count == expected_counts[label], label
        assert nearest == pytest.approx(expected_nearest[label], rel=1e-5)
    assert export["n_pairs"] == len(best)
    assert set(out.info["chains"]) == {"A", "B"}


def test_parameters_are_validated(tmp_path):
    form = _pdb_form(tmp_path, _ATOMS)
    with pytest.raises(StepError, match="cutoff must be in"):
        _run(form, cutoff=0.0)
    with pytest.raises(StepError, match="cutoff must be in"):
        _run(form, cutoff=11.0)
    with pytest.raises(StepError, match="min_contacts must not be negative"):
        _run(form, min_contacts=-1)
    with pytest.raises(StepError, match="a PDB form with dims"):
        _run(form, atom_dim="residue")
    with pytest.raises(StepError, match="no heavy atoms"):
        _run(form, exclude_resnames="ALA,GLY,SER,THR")


def test_single_residue_is_rejected(tmp_path):
    atoms = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CB", "ALA", "A", 1, 1.0, 0.0, 0.0),
    ]
    form = _pdb_form(tmp_path, atoms)
    with pytest.raises(StepError, match="at least two residues are required"):
        _run(form)


def test_residue_graph_helper():
    coords = np.asarray(
        [[0.0, 0.0, 0.0], [0.0, 0.0, 4.0], [3.0, 0.0, 0.0]], dtype=np.float64
    )
    residue_index = np.asarray([0, 1, 2], dtype=np.int64)
    chains = np.asarray(["A", "A", "B"], dtype=object)
    counts, nearest, pairs = residue_graph(coords, residue_index, chains, 4.5, False)
    np.testing.assert_array_equal(counts, [1, 0, 1])
    np.testing.assert_allclose(nearest[[0, 2]], [3.0, 3.0])
    assert np.isnan(nearest[1])
    assert pairs == [(0, 2, 3.0)]
