"""Tests for structure_secondary_structure."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.structure_secondary_structure import (
    StructureSecondaryStructureStep,
    assign_states,
    backbone_angles,
    dihedral,
    segment_rows,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _pdb_form(records):
    from src.reader.readers._encoder import LabelEncoder

    rows, chains, resnames, names = [], [], [], []
    for chain, resname, number, name, x, y, z in records:
        rows.append([x, y, z, 1.0, 0.0, float(number)])
        chains.append(chain)
        resnames.append(resname)
        names.append(name)
    numeric = np.asarray(rows, dtype=np.float64)
    matrix = np.column_stack(
        [
            numeric[:, 0],
            numeric[:, 1],
            numeric[:, 2],
            numeric[:, 3],
            numeric[:, 4],
            numeric[:, 5],
            LabelEncoder().fit_transform(chains),
            LabelEncoder().fit_transform(resnames),
            LabelEncoder().fit_transform(names),
        ]
    ).astype(np.float32)
    chain_encoder, resname_encoder, name_encoder = LabelEncoder(), LabelEncoder(), LabelEncoder()
    chain_encoder.fit_transform(chains)
    resname_encoder.fit_transform(resnames)
    name_encoder.fit_transform(names)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index + 1}": index for index in range(len(records))},
            "field": {
                "x": 0,
                "y": 1,
                "z": 2,
                "occupancy": 3,
                "bfactor": 4,
                "residue_number": 5,
                "chain": 6,
                "resname": 7,
                "atom_name": 8,
            },
        },
        info={
            "missing_code": float("nan"),
            "encoders": {
                "field": {"chain": chain_encoder, "resname": resname_encoder, "atom_name": name_encoder}
            },
        },
    )


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_dihedral_planar() -> None:
    p0 = np.array([0.0, 0.0, 0.0])
    p1 = np.array([1.0, 0.0, 0.0])
    p2 = np.array([1.0, 1.0, 0.0])
    p3 = np.array([0.0, 1.0, 0.0])
    value = abs(dihedral(p0, p1, p2, p3))
    assert min(value, abs(180.0 - value)) < 1e-6
    perpendicular = dihedral(p0, p1, p2, np.array([1.0, 1.0, 1.0]))
    assert abs(abs(perpendicular) - 90.0) < 1e-6


def test_assign_states_helix_and_strand() -> None:
    helix = np.asarray([[-60.0, -45.0]] * 9)
    assert assign_states(helix, window=3) == ["H"] * 9
    strand = np.asarray([[-120.0, 130.0]] * 9)
    assert assign_states(strand, window=3) == ["E"] * 9
    mixed = np.asarray([[-60.0, -45.0], [60.0, 60.0], [-120.0, 130.0]])
    assert assign_states(mixed, window=1) == ["H", "C", "E"]


def test_short_runs_demoted_to_coil() -> None:
    angles = np.asarray([[-60.0, -45.0], [-60.0, -45.0]] + [[60.0, 60.0]] * 6)
    states = assign_states(angles, window=5)
    assert states[0] == "C" and states[1] == "C"


def test_segment_rows() -> None:
    rows = segment_rows(["H", "H", "C", "E", "E", "E"], ["a", "b", "c", "d", "e", "f"])
    assert [row["state"] for row in rows] == ["H", "C", "E"]
    assert rows[0]["start"] == 1 and rows[0]["end"] == 2
    assert rows[2]["start"] == 4 and rows[2]["length"] == 3
    assert rows[2]["residues"] == ["d", "e", "f"]


def test_step_on_fixture() -> None:
    from pathlib import Path

    from src.reader import pick_reader, read_source

    path = Path(__file__).resolve().parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    form = read_source(path, dims=["atom", "field"], labels={"atom": "auto", "field": "auto"}, reader_id=None)
    out, export = _run(StructureSecondaryStructureStep(), {"window": 3}, form)
    assert list(out.dims) == ["segment", "statistic"]
    assert out.data.shape[1] == 3
    assert len(out.info["states"]) == 16
    assert out.info["states"].count("H") + out.info["states"].count("E") + out.info["states"].count("C") == 16
    assert export["n_residues"] == 16


def test_parameters_and_inputs() -> None:
    from pathlib import Path

    from src.reader import read_source

    path = Path(__file__).resolve().parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    form = read_source(path, dims=["atom", "field"], labels={"atom": "auto", "field": "auto"}, reader_id=None)
    with pytest.raises(StepError, match="window must be between"):
        _run(StructureSecondaryStructureStep(), {"window": 0}, form)
    with pytest.raises(StepError, match="min_helix_fraction"):
        _run(StructureSecondaryStructureStep(), {"min_helix_fraction": 0.0}, form)
    with pytest.raises(StepError, match="min_strand_fraction"):
        _run(StructureSecondaryStructureStep(), {"min_strand_fraction": 1.5}, form)

    two = Form(
        data=np.zeros((4, 3), dtype=np.float32),
        dims=["atom", "bogus"],
        labels={"atom": {str(index): index for index in range(4)}, "bogus": {"x": 0, "y": 1, "z": 2}},
        info={"missing_code": float("nan")},
    )
    with pytest.raises(StepError, match="structure form with dims"):
        _run(StructureSecondaryStructureStep(), {}, two)
