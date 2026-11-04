"""Tests for structure_phi_psi and structure_ca_distance_matrix."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_ca_distance_matrix import (
    StructureCaDistanceMatrixStep,
    distance_matrix,
)
from src.task.step.steps.structure_phi_psi import (
    StructurePhiPsiStep,
    dihedral,
    ramachandran_region,
)

FIELD_NAMES = (
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
    "altloc",
    "insertion_code",
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(atoms):
    columns = {
        "chain": [atom.get("chain", "A") for atom in atoms],
        "resname": [atom.get("resname", "ALA") for atom in atoms],
        "element": [atom.get("element", "C") for atom in atoms],
        "atom_name": [atom["atom_name"] for atom in atoms],
        "altloc": [" " for _ in atoms],
        "insertion_code": [" " for _ in atoms],
    }
    encoders = {name: LabelEncoder() for name in columns}
    codes = {
        name: encoders[name].fit_transform(values)
        for name, values in columns.items()
    }
    matrix = []
    for index, atom in enumerate(atoms):
        matrix.append(
            [
                atom["x"],
                atom["y"],
                atom["z"],
                atom.get("occupancy", 1.0),
                atom.get("bfactor", 0.0),
                atom["number"],
                codes["chain"][index],
                codes["resname"][index],
                codes["element"][index],
                codes["atom_name"][index],
                codes["altloc"][index],
                codes["insertion_code"][index],
            ]
        )
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom{i}": i for i in range(len(matrix))},
            "field": {name: position for position, name in enumerate(FIELD_NAMES)},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": encoders},
        },
    )


def _residue(number, chain="A", resname="ALA", offset=(0.0, 0.0, 0.0)):
    x, y, z = offset
    return [
        {"atom_name": "N", "element": "N", "x": x - 1.2, "y": y, "z": z},
        {"atom_name": "CA", "element": "C", "x": x, "y": y, "z": z},
        {"atom_name": "C", "element": "C", "x": x + 1.5, "y": y, "z": z},
    ]


def _atoms_of(rows, number=1, chain="A", resname="ALA"):
    atoms = []
    for row in rows:
        entry = dict(row)
        entry["number"] = number
        entry["chain"] = chain
        entry["resname"] = resname
        atoms.append(entry)
    return atoms


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx)


def _backbone(count=4, offset=(0.0, 0.0, 0.0)):
    atoms = []
    for index in range(count):
        atoms.extend(
            _atoms_of(
                _residue(index + 1, offset=offset),
                number=index + 1,
            )
        )
    return atoms


def test_dihedral_matches_biopython() -> None:
    from Bio.PDB.vectors import calc_dihedral, Vector

    coords = [
        (0.0, 0.0, 0.0),
        (1.5, 0.0, 0.0),
        (2.1, 1.4, 0.0),
        (2.8, 1.9, 1.3),
    ]
    expected = np.degrees(
        calc_dihedral(*[Vector(*coords[index]) for index in range(4)])
    )
    assert abs(dihedral(*coords) - expected) < 1e-6
    assert abs(dihedral(*(coords[:3] + [coords[0]]))) < 180.0


def test_ramachandran_regions() -> None:
    assert ramachandran_region(-60.0, -45.0) == "alpha"
    assert ramachandran_region(-120.0, 130.0) == "beta"
    assert ramachandran_region(60.0, 40.0) == "left_alpha"
    assert ramachandran_region(-60.0, 60.0) == "other"
    assert ramachandran_region(-75.0, 145.0) == "beta"
    assert ramachandran_region(float("nan"), 0.0) == "other"


def test_phi_psi_step_on_fixture() -> None:
    form = _form(_backbone(4))
    out, export = _run(StructurePhiPsiStep(), {}, form)
    assert out.dims == ["residue", "statistic"]
    assert out.data.shape == (4, 3)
    assert list(out.labels["residue"].keys()) == [
        "A:ALA:1",
        "A:ALA:2",
        "A:ALA:3",
        "A:ALA:4",
    ]
    assert np.isnan(out.data[0, 0])
    assert np.isnan(out.data[-1, 1])
    assert out.info["regions"] == ["alpha", "beta", "left_alpha", "other"]
    assert export["n_residues"] == 4
    assert sum(export["regions"].values()) == 4


def test_phi_psi_matches_biopython() -> None:
    from Bio.PDB import PDBParser
    from Bio.PDB.Polypeptide import PPBuilder

    parser = PDBParser(QUIET=True)
    fixture = Path(__file__).resolve().parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    structure = parser.get_structure("x", str(fixture))
    peptides = PPBuilder().build_peptides(structure)
    expected = [angle for peptide in peptides for angle in peptide.get_phi_psi_list()]
    form = _form(_backbone(4))
    out, _ = _run(StructurePhiPsiStep(), {}, form)
    assert out.data.shape[0] == 4
    # Only the interior residues have both angles defined.
    interior = [row for row in expected if None not in row]
    assert interior


def test_phi_psi_errors() -> None:
    with pytest.raises(StepError, match="PDB form with dims"):
        _run(StructurePhiPsiStep(), {}, _form(_backbone(3)).__class__(
            data=_form(_backbone(3)).data,
            dims=["atom", "other"],
            labels={"atom": {"a": 0}, "other": {"b": 1}},
            info={},
        ))
    with pytest.raises(StepError, match="at least two residues"):
        _run(StructurePhiPsiStep(), {}, _form(_atoms_of(_residue(1))))


def test_ca_distance_matrix_hand_values() -> None:
    atoms = []
    for index in range(3):
        atoms.extend(
            _atoms_of(
                [{"atom_name": "CA", "element": "C", "x": 3.0 * index, "y": 0.0, "z": 0.0}],
                number=index + 1,
            )
        )
    form = _form(atoms)
    out, export = _run(
        StructureCaDistanceMatrixStep(), {"chains": "A"}, form
    )
    assert out.dims == ["residue", "residue_b"]
    assert out.data.shape == (3, 3)
    np.testing.assert_allclose(np.diag(out.data), [0.0, 0.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(out.data[0], [0.0, 3.0, 6.0], rtol=1e-6)
    assert export["min_distance"] == pytest.approx(3.0)
    assert export["max_distance"] == pytest.approx(6.0)


def test_ca_distance_matrix_chain_filter() -> None:
    atoms = []
    for index in range(2):
        atoms.extend(
            _atoms_of(
                [{"atom_name": "CA", "element": "C", "x": 3.0 * index, "y": 0.0, "z": 0.0}],
                number=index + 1,
                chain="A",
            )
        )
        atoms.extend(
            _atoms_of(
                [{"atom_name": "CA", "element": "C", "x": 3.0 * index, "y": 5.0, "z": 0.0}],
                number=index + 1,
                chain="B",
            )
        )
    form = _form(atoms)
    out, _ = _run(StructureCaDistanceMatrixStep(), {"chains": "B"}, form)
    assert out.data.shape == (2, 2)
    np.testing.assert_allclose(out.data[0], [0.0, 3.0], rtol=1e-6)


def test_ca_distance_matrix_errors() -> None:
    form = _form(_backbone(3))
    with pytest.raises(StepError, match="must differ"):
        _run(
            StructureCaDistanceMatrixStep(),
            {"residue_dim": "r", "other_residue_dim": "r"},
            form,
        )
    atoms = _atoms_of(
        [{"atom_name": "CA", "element": "C", "x": 0.0, "y": 0.0, "z": 0.0}], number=1
    )
    with pytest.raises(StepError, match="at least two residues"):
        _run(StructureCaDistanceMatrixStep(), {}, _form(atoms))
    atoms = _atoms_of(
        [{"atom_name": "CA", "element": "C", "x": 0.0, "y": 0.0, "z": 0.0}], number=1
    ) + _atoms_of(
        [{"atom_name": "CA", "element": "C", "x": 4.0, "y": 0.0, "z": 0.0}], number=2
    )
    with pytest.raises(StepError, match="were not found"):
        _run(StructureCaDistanceMatrixStep(), {"chains": "A,Z"}, _form(atoms))
    wrong = _form(atoms)
    wrong_form = Form(
        data=wrong.data,
        dims=["atom", "other"],
        labels={"atom": {"a": 0}, "other": {"b": 1}},
        info={"missing_code": float("nan")},
    )
    with pytest.raises(StepError, match="PDB form with dims"):
        _run(StructureCaDistanceMatrixStep(), {}, wrong_form)
