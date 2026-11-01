"""Tests for structure_contact_order."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.structure_contact_order import (
    StructureContactOrderStep,
    ca_coordinates,
    contact_order,
    contact_pairs,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _pdb_form(ca_positions):
    """Minimal PDB form with one CA atom per residue on chain A."""

    from src.reader.readers._encoder import LabelEncoder

    chains, resnames, numbers, names = [], [], [], []
    rows = []
    for index, position in enumerate(ca_positions):
        chains.append("A")
        resnames.append("ALA")
        numbers.append(float(index + 1))
        names.append("CA")
        rows.append([float(position[0]), float(position[1]), float(position[2]), 1.0, 0.0, float(index + 1)])
    matrix = np.asarray(rows, dtype=np.float32)
    chain_encoder = LabelEncoder()
    resname_encoder = LabelEncoder()
    name_encoder = LabelEncoder()
    matrix = np.column_stack(
        [
            matrix[:, 0],
            matrix[:, 1],
            matrix[:, 2],
            matrix[:, 3],
            matrix[:, 4],
            matrix[:, 5],
            chain_encoder.fit_transform(chains),
            resname_encoder.fit_transform(resnames),
            name_encoder.fit_transform(names),
        ]
    ).astype(np.float32)
    labels = {f"atom:{index + 1}": index for index in range(len(ca_positions))}
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={"atom": labels, "field": {"x": 0, "y": 1, "z": 2, "occupancy": 3, "bfactor": 4, "residue_number": 5, "chain": 6, "resname": 7, "atom_name": 8}},
        info={
            "missing_code": float("nan"),
            "encoders": {"field": {"chain": chain_encoder, "resname": resname_encoder, "atom_name": name_encoder}},
        },
    )


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[ctx.step_params["output"]], step.export(ctx)


FOLDED = [(0.0, 0.0, 0.0), (3.8, 0.0, 0.0), (7.6, 0.0, 0.0), (10.0, 0.0, 0.0), (0.5, 0.0, 0.0)]


def test_contact_pairs_hand_counts() -> None:
    ca, residues = ca_coordinates(
        np.asarray([[0, 0, 0], [3.8, 0, 0], [7.6, 0, 0], [10.0, 0, 0], [0.5, 0, 0]], dtype=float),
        ["A:ALA:1", "A:ALA:2", "A:ALA:3", "A:ALA:4", "A:ALA:5"],
        np.asarray(["CA"] * 5),
    )
    assert residues == ["A:ALA:1", "A:ALA:2", "A:ALA:3", "A:ALA:4", "A:ALA:5"]
    pairs = contact_pairs(ca, 4.5, 3)
    assert pairs == [(0, 4), (1, 4)]


def test_contact_order_hand_values() -> None:
    ca = np.asarray([[0, 0, 0], [3.8, 0, 0], [7.6, 0, 0], [10.0, 0, 0], [0.5, 0, 0]], dtype=float)
    rows, absolute, relative, n_pairs = contact_order(ca, 4.5, 3)
    assert n_pairs == 2
    assert rows["contacts"] == [1, 1, 0, 0, 2]
    assert absolute == pytest.approx(3.5 / 5)
    assert relative == pytest.approx(3.5)
    assert rows["mean_separation"][0] == pytest.approx(4.0)
    assert rows["mean_separation"][1] == pytest.approx(3.0)
    assert np.isnan(rows["mean_separation"][2])


def test_step_output_and_export() -> None:
    form = _pdb_form(FOLDED)
    out, export = _run(StructureContactOrderStep(), {"cutoff": 4.5, "min_separation": 3}, form)
    assert list(out.dims) == ["residue", "statistic"]
    assert out.data.shape == (5, 2)
    assert out.data[:, 0].tolist() == [1.0, 1.0, 0.0, 0.0, 2.0]
    assert out.info["n_contacts"] == 2
    assert out.info["relative_contact_order"] == pytest.approx(3.5)
    assert export["n_residues"] == 5
    assert export["absolute_contact_order"] == pytest.approx(0.7, abs=1e-6)


def test_brute_force_oracle() -> None:
    rng = np.random.default_rng(7)
    positions = rng.normal(scale=6.0, size=(9, 3))
    form = _pdb_form([tuple(row) for row in positions])
    out, _ = _run(StructureContactOrderStep(), {"cutoff": 8.0, "min_separation": 2}, form)
    coords = np.vstack([entries for entries in [positions]])
    expected = 0
    separations = []
    for left in range(len(coords)):
        for right in range(left + 1, len(coords)):
            if right - left < 2:
                continue
            if np.linalg.norm(coords[right] - coords[left]) <= 8.0:
                expected += 1
                separations.append(right - left)
    assert out.info["n_contacts"] == expected
    if separations:
        assert out.info["relative_contact_order"] == pytest.approx(float(np.mean(separations)), abs=1e-6)


def test_tighter_cutoff_and_separation() -> None:
    form = _pdb_form(FOLDED)
    with pytest.raises(StepError, match="no residue pair"):
        _run(StructureContactOrderStep(), {"cutoff": 3.0, "min_separation": 5}, form)


def test_parameters() -> None:
    form = _pdb_form(FOLDED)
    with pytest.raises(StepError, match="cutoff must be between"):
        _run(StructureContactOrderStep(), {"cutoff": 0.5}, form)
    with pytest.raises(StepError, match="cutoff must be between"):
        _run(StructureContactOrderStep(), {"cutoff": 25.0}, form)
    with pytest.raises(StepError, match="min_separation must be at least 1"):
        _run(StructureContactOrderStep(), {"min_separation": 0}, form)


def test_input_errors() -> None:
    plain = Form(
        data=np.zeros((3, 2), dtype=np.float32),
        dims=["x", "y"],
        labels={"x": {"a": 0, "b": 1, "c": 2}, "y": {"u": 0, "v": 1}},
        info={"missing_code": float("nan")},
    )
    with pytest.raises(StepError, match="dims"):
        _run(StructureContactOrderStep(), {}, plain)
    with pytest.raises(StepError, match="at least three CA"):
        _run(StructureContactOrderStep(), {}, _pdb_form(FOLDED[:2]))
