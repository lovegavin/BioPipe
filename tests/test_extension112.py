"""Hand-computed interface and ligand contact checks on a tiny PDB fixture."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps.ligand_contact_profile import LigandContactProfileStep
from src.task.step.steps.minibinder_interface import MinibinderInterfaceStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(record, serial, name, altloc, resname, chain, number, x, y, z, element,
          icode=" "):
    return (
        f"{record:<6}{serial:5d} {name:^4}{altloc:1}{resname:>3} {chain:1}"
        f"{number:4d}{icode:1}   "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}          "
        f"{element:>2}"
    )


def _fixture(tmp_path):
    lines = [
        _atom("ATOM", 1, "CA", " ", "ALA", "A", 1, 0.0, 0.0, 3.0, "C"),
        _atom("ATOM", 2, "CA", " ", "GLY", "A", 2, 3.0, 0.0, 0.0, "C"),
        _atom("ATOM", 3, "CA", " ", "THR", "A", 3, 0.0, 0.0, 10.0, "C"),
        _atom("ATOM", 4, "CA", " ", "SER", "B", 1, 0.0, 0.0, 4.0, "C"),
        _atom("ATOM", 5, "CA", " ", "SER", "B", 2, 0.0, 0.0, 6.0, "C"),
        _atom("HETATM", 20, "C1", " ", "LIG", "L", 1, 0.0, 0.0, 0.0, "C"),
        _atom("HETATM", 21, "C2", " ", "LIG", "L", 1, 2.0, 0.0, 0.0, "C"),
        _atom("HETATM", 22, "O3", " ", "LIG", "L", 1, 0.0, 0.0, 2.0, "O"),
        _atom("HETATM", 23, "O", " ", "HOH", "W", 1, 0.0, 0.0, 1.0, "O"),
    ]
    path = tmp_path / "tiny_complex.pdb"
    path.write_text("\n".join(lines) + "\nEND\n", encoding="utf-8")
    reader = PdbReader()
    return path, reader.read(
        path, ["atom", "field"], {"atom": "auto", "field": "builtin"}
    )


def _run(step, form, params):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"]


def test_minibinder_interface_hand(tmp_path):
    _, form = _fixture(tmp_path)
    out = _run(
        MinibinderInterfaceStep(),
        form,
        {"binder_chains": "A", "target_chains": "B", "cutoff": 5.0},
    )
    assert list(out.dims) == ["residue", "statistic"]
    assert out.labels["residue"] == {
        "A:ALA:1": 0,
        "A:THR:3": 1,
        "A:GLY:2": 2,
    }
    np.testing.assert_allclose(
        out.data,
        [[2.0, 1.0], [1.0, 4.0], [1.0, 5.0]],
        rtol=1e-5,
        atol=1e-5,
    )
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["B"]
    assert out.info["n_target_residues"] == 2
    assert out.info["n_binder_residues"] == 3
    assert out.info["n_interface_residues"] == 3


def test_minibinder_derives_target_chain(tmp_path):
    _, form = _fixture(tmp_path)
    out = _run(
        MinibinderInterfaceStep(),
        form,
        {"binder_chains": "A", "target_chains": "", "cutoff": 5.0},
    )
    # Every other chain is derived as target, including the non-polymer ligand
    # chain L; pass target_chains explicitly to keep ligands out.
    assert out.info["target_chains"] == ["B", "L"]
    assert out.labels["residue"] == {"A:ALA:1": 0, "A:GLY:2": 1, "A:THR:3": 2}


def test_minibinder_errors(tmp_path):
    _, form = _fixture(tmp_path)
    with pytest.raises(StepError, match="set binder_chains and/or target_chains"):
        _run(MinibinderInterfaceStep(), form, {})
    with pytest.raises(StepError, match="not found in structure"):
        _run(MinibinderInterfaceStep(), form, {"binder_chains": "Z"})
    with pytest.raises(StepError, match="overlap"):
        _run(
            MinibinderInterfaceStep(),
            form,
            {"binder_chains": "A", "target_chains": "A,B"},
        )
    with pytest.raises(StepError, match="no binder residue has at least"):
        _run(
            MinibinderInterfaceStep(),
            form,
            {"binder_chains": "A", "target_chains": "B", "cutoff": 0.5},
        )
    with pytest.raises(StepError, match="cutoff must be"):
        _run(
            MinibinderInterfaceStep(),
            form,
            {"binder_chains": "A", "target_chains": "B", "cutoff": 0.0},
        )


def test_ligand_contact_profile_hand(tmp_path):
    _, form = _fixture(tmp_path)
    out = _run(
        LigandContactProfileStep(),
        form,
        {"ligand_resname": "LIG", "cutoff": 3.5},
    )
    assert list(out.dims) == ["atom", "statistic"]
    assert out.labels["atom"] == {"atom:20": 0, "atom:21": 1, "atom:22": 2}
    np.testing.assert_allclose(
        out.data,
        [[2.0, 3.0], [1.0, 1.0], [2.0, 1.0]],
        rtol=1e-5,
        atol=1e-5,
    )
    assert out.info["n_ligand_atoms"] == 3
    assert out.info["nearest_residue"] == [
        "A:ALA:1",
        "A:GLY:2",
        "A:ALA:1",
    ]
    assert out.info["contact_residues"][1] == ["A:GLY:2"]
    assert out.info["contact_residues"][2] == ["A:ALA:1", "B:SER:1"]


def test_ligand_errors(tmp_path):
    _, form = _fixture(tmp_path)
    with pytest.raises(StepError, match="no ligand atoms named"):
        _run(LigandContactProfileStep(), form, {"ligand_resname": "ATP"})
    with pytest.raises(StepError, match="ligand_resname is required"):
        _run(LigandContactProfileStep(), form, {"ligand_resname": ""})
    with pytest.raises(StepError, match="cutoff must be"):
        _run(
            LigandContactProfileStep(),
            form,
            {"ligand_resname": "LIG", "cutoff": -1.0},
        )


def test_ligand_excludes_water(tmp_path):
    _, form = _fixture(tmp_path)
    out = _run(
        LigandContactProfileStep(),
        form,
        {"ligand_resname": "LIG", "cutoff": 3.5, "exclude_resnames": "HOH,WAT"},
    )
    # Water at (0, 0, 1) is 1 A from O3 but must not appear as a contact.
    assert "W:HOH:1" not in out.info["contact_residues"][2]
