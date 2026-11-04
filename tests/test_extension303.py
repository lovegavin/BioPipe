"""structure_ligand_geometry_qc: RDKit bounds and clash checks."""

import numpy as np
import pytest

pytest.importorskip("rdkit")

from rdkit import Chem
from rdkit.Chem import AllChem

from src.core.errors import StepError
from src.core.forms import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_geometry_qc import bond_outliers, clash_summary

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _benzene():
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccccc1"))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    AllChem.MMFFOptimizeMolecule(mol)
    conformer = mol.GetConformer()
    rows = []
    for index, atom in enumerate(mol.GetAtoms()):
        position = conformer.GetAtomPosition(index)
        rows.append((position.x, position.y, position.z, 1, "LIG", "A", f"{atom.GetSymbol()}{index}", atom.GetSymbol()))
    return mol, np.asarray([[row[0], row[1], row[2]] for row in rows])


def _form(rows):
    encoders = {}
    data = []
    for name_index, name in enumerate(COLUMNS):
        if name in ("x", "y", "z", "residue_number"):
            continue
        encoders[name] = LabelEncoder()
        encoders[name].fit_transform([str(row[name_index]) for row in rows])
    for row in rows:
        values = []
        for name, value in zip(COLUMNS, row):
            if name in ("x", "y", "z", "residue_number"):
                values.append(float(value))
            else:
                values.append(float(encoders[name].mapping[str(value)]))
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {f"a{i}": i for i in range(len(rows))}, "field": {name: i for i, name in enumerate(COLUMNS)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_bond_outliers_zero_for_ideal_geometry():
    mol, coordinates = _benzene()
    outliers, worst = bond_outliers(mol, coordinates)
    assert outliers == []
    assert worst < 0.05


def test_bond_outliers_flag_stretched_bond():
    mol, coordinates = _benzene()
    moved = coordinates.copy()
    moved[1] += np.array([1.4, 0.0, 0.0])
    outliers, worst = bond_outliers(mol, moved)
    assert outliers
    assert worst > 0.2


def test_clash_summary():
    ligand = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
    protein = np.array([[1.0, 0.0, 0.0], [5.0, 3.0, 0.0]])
    clashes, minimum = clash_summary(ligand, protein, 2.0)
    assert clashes == 1
    assert minimum == pytest.approx(1.0)


def test_run_reports_geometry(tmp_path):
    mol, coordinates = _benzene()
    conformer = mol.GetConformer()
    rows = [
        (position.x, position.y, position.z, 1, "LIG", "A", f"{atom.GetSymbol()}{index}", atom.GetSymbol())
        for index, atom in ((i, mol.GetAtomWithIdx(i)) for i in range(mol.GetNumAtoms()))
        for position in [conformer.GetAtomPosition(index)]
    ]
    form = _form(rows)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_ligand_geometry_qc", "inputs": ["pdb"], "params": {"output": "qc", "ligand_resname": "LIG"}}])
    result = ctx["qc"]
    assert result.dims == ["ligand", "statistic"]
    assert result.data.shape == (1, 6)
    assert result.data[0, 2] == 0.0
    assert result.data[0, 0] == 12.0


def test_errors(tmp_path):
    _mol, coordinates = _benzene()
    rows = [(x, y, z, 1, "LIG", "A", f"X{i}", "C") for i, (x, y, z) in enumerate(coordinates)]
    form = _form(rows)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="no atoms match"):
        run(ctx, [{"name": "structure_ligand_geometry_qc", "inputs": ["pdb"], "params": {"output": "qc", "ligand_resname": "XXX"}}])
