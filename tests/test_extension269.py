from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context import Context
from src.task.runner import run


def _ctx(task_dir: Path, out_name: str, params: dict) -> Context:
    ctx = Context(str(task_dir / "task"), {"params": {}})
    ctx.step_params = {"output": out_name, **params}
    return ctx

from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.structure_ligand_strain import ligand_block, strain_energy

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem
from rdkit.Chem import AllChem

COLUMNS = ("x", "y", "z", "resname", "chain", "residue_number", "element", "atom_name")


def _ligand_mol(smiles="CCO"):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    AllChem.MMFFOptimizeMolecule(mol, maxIters=2000)
    return mol


def _form(mol, resname="LIG") -> Form:
    conformer = mol.GetConformer()
    encoders = {name: LabelEncoder() for name in COLUMNS}
    raw = {}
    for atom in mol.GetAtoms():
        position = conformer.GetAtomPosition(atom.GetIdx())
        raw.setdefault("x", []).append(position.x)
        raw.setdefault("y", []).append(position.y)
        raw.setdefault("z", []).append(position.z)
        raw.setdefault("resname", []).append(resname)
        raw.setdefault("chain", []).append("A")
        raw.setdefault("residue_number", []).append(1)
        raw.setdefault("element", []).append(atom.GetSymbol().upper())
        raw.setdefault("atom_name", []).append(atom.GetSymbol().upper())
    encoded = ("resname", "chain", "atom_name", "element")
    columns = {}
    for name in COLUMNS:
        if name in encoded:
            columns[name] = encoders[name].fit_transform(raw[name])
        else:
            columns[name] = np.asarray(raw[name], dtype=np.float32)
    data = np.stack([columns[name] for name in COLUMNS], axis=1).astype(np.float32)
    n_atoms = data.shape[0]
    return Form(
        data=data,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom{i + 1}": i for i in range(n_atoms)},
            "field": {name: i for i, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_ligand_block_renders_the_selected_residue():
    form = _form(_ligand_mol())
    block, n_atoms = ligand_block(form, "atom", "field", "LIG")
    assert n_atoms == form.data.shape[0]
    assert block.count("HETATM") == n_atoms
    assert block.splitlines()[0][76:78].strip() in ("C", "O", "H")


def test_relaxed_conformation_has_small_strain():
    form = _form(_ligand_mol())
    block, _n = ligand_block(form, "atom", "field", "LIG")
    bound, minimized, strain = strain_energy(block)
    assert minimized <= bound + 1e-3
    assert abs(strain) < 5.0


def test_distorted_conformation_has_positive_strain():
    mol = _ligand_mol()
    conformer = mol.GetConformer()
    position = conformer.GetAtomPosition(1)
    conformer.SetAtomPosition(1, (position.x + 0.8, position.y, position.z))
    form = _form(mol)
    block, _n = ligand_block(form, "atom", "field", "LIG")
    bound, minimized, strain = strain_energy(block)
    assert strain > 1.0
    assert minimized < bound


def test_missing_ligand_is_rejected():
    form = _form(_ligand_mol(), resname="XYZ")
    with pytest.raises(StepError, match="no residue named 'LIG'"):
        ligand_block(form, "atom", "field", "LIG")


def test_run_reports_one_ligand_row(tmp_path):
    form = _form(_ligand_mol())
    params = {"ligand_resname": "LIG"}
    ctx = _ctx(tmp_path, "strain", params)
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_ligand_strain", "inputs": ["pdb"], "params": params}])
    result = ctx["strain"]
    assert result.data.shape == (1, 3)
    assert result.dims == ["ligand", "statistic"]
    assert result.info["resname"] == "LIG"
    assert result.info["force_field"] == "MMFF94"
