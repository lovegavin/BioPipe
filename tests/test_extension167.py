"""Tests for structure_disulfide_bonds."""
from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_disulfide_bonds import (
    StructureDisulfideBondsStep,
    disulfide_pairs,
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


def _atom(chain, resname, number, atom_name, x, y, z, element="S"):
    return {
        "chain": chain,
        "resname": resname,
        "residue_number": number,
        "atom_name": atom_name,
        "x": x,
        "y": y,
        "z": z,
        "element": element,
    }


def _pdb_form(atoms: list[dict]) -> Form:
    matrix = np.asarray(
        [
            [
                atom["x"],
                atom["y"],
                atom["z"],
                1.0,
                10.0,
                atom["residue_number"],
                atom["chain"],
                atom["resname"],
                atom["element"],
                atom["atom_name"],
            ]
            for atom in atoms
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


def _fixture() -> list[dict]:
    return [
        _atom("A", "CYS", 26, "SG", 0.0, 0.0, 0.0),
        _atom("A", "CYS", 26, "CB", 1.0, 0.0, 0.0, "C"),
        _atom("B", "CYS", 84, "SG", 2.0, 0.0, 0.0),
        _atom("A", "CYS", 40, "SG", 10.0, 10.0, 10.0),
        _atom("A", "ALA", 50, "CB", 5.0, 5.0, 5.0, "C"),
    ]


def test_disulfide_pairs_hand() -> None:
    coordinates = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [10.0, 10.0, 10.0]])
    labels = np.array(["A:CYS:26", "B:CYS:84", "A:CYS:40"], dtype=object)
    pairs = disulfide_pairs(coordinates, labels, 2.5)
    assert len(pairs) == 1
    assert pairs[0]["bond"] == "A:CYS:26-B:CYS:84"
    assert pairs[0]["distance"] == pytest.approx(2.0)


def test_step_output() -> None:
    ctx = Ctx({"max_distance": 2.5, "output": "disulfides"})
    step = StructureDisulfideBondsStep()
    step.run(ctx, [_pdb_form(_fixture())])
    out = ctx["disulfides"]
    assert out.data.shape == (1, 1)
    assert list(out.labels["bond"]) == ["A:CYS:26-B:CYS:84"]
    assert out.data[0, 0] == pytest.approx(2.0, abs=1e-6)
    assert out.info["n_bonds"] == 1
    assert out.info["n_cysteines"] == 3
    assert out.info["free_cysteines"] == ["A:CYS:40"]
    exported = step.export(ctx)
    assert exported["n_bonds"] == 1
    assert exported["free_cysteines"] == ["A:CYS:40"]


def test_biopython_oracle() -> None:
    pytest.importorskip("Bio.PDB")
    from Bio.PDB.Atom import Atom
    from Bio.PDB.NeighborSearch import NeighborSearch
    sulphur = [atom for atom in _fixture() if atom["atom_name"] == "SG"]
    labels = [f"{atom['chain']}:CYS:{atom['residue_number']}" for atom in sulphur]
    atoms = [
        Atom(
            "SG",
            np.array([atom["x"], atom["y"], atom["z"]], dtype=np.float32),
            10.0,
            1.0,
            " ",
            " SG ",
            index + 1,
            "S",
        )
        for index, atom in enumerate(sulphur)
    ]
    search = NeighborSearch(atoms)
    oracle = {
        tuple(sorted((labels[first.get_serial_number() - 1], labels[second.get_serial_number() - 1])))
        for first, second in search.search_all(2.5, level="A")
    }
    coordinates = np.array([[atom["x"], atom["y"], atom["z"]] for atom in sulphur])
    ours = {
        tuple(pair["bond"].split("-"))
        for pair in disulfide_pairs(coordinates, np.array(labels, dtype=object), 2.5)
    }
    assert ours == oracle


def test_tighter_cutoff_gives_empty_result() -> None:
    ctx = Ctx({"max_distance": 1.5, "output": "out"})
    StructureDisulfideBondsStep().run(ctx, [_pdb_form(_fixture())])
    assert ctx["out"].data.shape == (0, 1)
    assert ctx["out"].info["n_bonds"] == 0


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="max_distance must be between 1.5 and 4.0"):
        StructureDisulfideBondsStep().run(
            Ctx({"max_distance": 9.0}), [_pdb_form(_fixture())]
        )
    with pytest.raises(StepError, match="a PDB form with dims"):
        StructureDisulfideBondsStep().run(
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
    no_sg = [_atom("A", "ALA", 1, "CA", 0.0, 0.0, 0.0, "C")]
    with pytest.raises(StepError, match="no cysteine SG atoms"):
        StructureDisulfideBondsStep().run(Ctx({}), [_pdb_form(no_sg)])
