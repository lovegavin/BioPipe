"""Tests for structure_salt_bridges."""
from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_salt_bridges import (
    StructureSaltBridgesStep,
    charged_centroids,
    salt_bridges,
)

FIELDS = (
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
)
STRING_FIELDS = ("chain", "resname", "element", "atom_name")


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _pdb_form(atoms: list[tuple]) -> Form:
    matrix = np.asarray(
        [
            [x, y, z, 1.0, 10.0, number, chain, resname, element, atom_name]
            for chain, resname, number, atom_name, x, y, z, element in atoms
        ],
        dtype=object,
    )
    for numeric in ("x", "y", "z", "occupancy", "bfactor", "residue_number"):
        index = FIELDS.index(numeric)
        matrix[:, index] = matrix[:, index].astype(float)
    encoders = {}
    for name in STRING_FIELDS:
        index = FIELDS.index(name)
        encoder = LabelEncoder()
        matrix[:, index] = encoder.fit_transform([str(value[index]) for value in matrix])
        encoders[name] = encoder
    matrix = matrix.astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index + 1}": index for index in range(len(matrix))},
            "field": {name: index for index, name in enumerate(FIELDS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _fixture() -> list[tuple]:
    return [
        ("A", "ASP", 1, "OD1", 0.0, 0.0, 0.0, "O"),
        ("A", "ASP", 1, "OD2", 1.0, 0.0, 0.0, "O"),
        ("B", "LYS", 5, "NZ", 4.5, 0.0, 0.0, "N"),
        ("C", "ARG", 10, "CZ", 20.0, 0.0, 0.0, "C"),
        ("C", "ARG", 10, "NH1", 20.0, 1.0, 0.0, "N"),
        ("C", "ARG", 10, "NH2", 20.0, 0.0, 1.0, "N"),
        ("A", "ALA", 2, "CA", 0.0, 5.0, 0.0, "C"),
    ]


def test_centroids_and_pairs() -> None:
    atoms = _fixture()
    resnames = np.array([atom[1] for atom in atoms], dtype=object)
    atom_names = np.array([atom[3] for atom in atoms], dtype=object)
    labels = np.array(
        [f"{atom[0]}:{atom[1]}:{atom[2]}" for atom in atoms], dtype=object
    )
    coordinates = np.array([[atom[4], atom[5], atom[6]] for atom in atoms])
    residues = charged_centroids(coordinates, resnames, atom_names, labels)
    by_label = {row["label"]: row for row in residues}
    assert by_label["A:ASP:1"]["group"] == "anion"
    assert by_label["A:ASP:1"]["centroid"] == pytest.approx([0.5, 0.0, 0.0])
    assert by_label["B:LYS:5"]["group"] == "cation"
    pairs = salt_bridges(residues, 4.0)
    assert [pair["bridge"] for pair in pairs] == ["A:ASP:1-B:LYS:5"]
    assert pairs[0]["distance"] == pytest.approx(4.0)


def test_step_output() -> None:
    ctx = Ctx({"max_distance": 4.0, "output": "bridges"})
    step = StructureSaltBridgesStep()
    step.run(ctx, [_pdb_form(_fixture())])
    out = ctx["bridges"]
    assert out.data.shape == (1, 1)
    assert list(out.labels["bridge"]) == ["A:ASP:1-B:LYS:5"]
    assert out.data[0, 0] == pytest.approx(4.0, abs=1e-6)
    assert out.info["n_bridges"] == 1
    assert out.info["n_inter"] == 1
    assert out.info["n_intra"] == 0
    assert out.info["anions"] == ["A:ASP:1"]
    assert out.info["cations"] == ["B:LYS:5", "C:ARG:10"]
    exported = step.export(ctx)
    assert exported["n_bridges"] == 1
    assert exported["max_distance"] == 4.0


def test_intra_chain_flag() -> None:
    atoms = [
        ("A", "ASP", 1, "OD1", 0.0, 0.0, 0.0, "O"),
        ("A", "LYS", 2, "NZ", 3.0, 0.0, 0.0, "N"),
    ]
    ctx = Ctx({"max_distance": 4.0, "output": "out"})
    StructureSaltBridgesStep().run(ctx, [_pdb_form(atoms)])
    assert ctx["out"].info["n_intra"] == 1
    assert ctx["out"].info["n_inter"] == 0


def test_tighter_cutoff_empties_result() -> None:
    ctx = Ctx({"max_distance": 2.0, "output": "out"})
    StructureSaltBridgesStep().run(ctx, [_pdb_form(_fixture())])
    assert ctx["out"].data.shape == (0, 1)
    assert ctx["out"].info["n_bridges"] == 0


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="max_distance must be between 2.0 and 10.0"):
        StructureSaltBridgesStep().run(
            Ctx({"max_distance": 20.0}), [_pdb_form(_fixture())]
        )
    neutral = [("A", "ALA", 1, "CA", 0.0, 0.0, 0.0, "C")]
    with pytest.raises(StepError, match="no charged residues"):
        StructureSaltBridgesStep().run(Ctx({}), [_pdb_form(neutral)])
    with pytest.raises(StepError, match="a PDB form with dims"):
        StructureSaltBridgesStep().run(
            Ctx({}),
            [
                Form(
                    data=np.zeros((2, 2), dtype=np.float32),
                    dims=["atom", "value"],
                    labels={"atom": {"a": 0, "b": 1}, "value": {"v": 0, "w": 1}},
                    info={"missing_code": np.nan},
                )
            ],
        )
