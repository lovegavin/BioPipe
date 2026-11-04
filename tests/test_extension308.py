"""structure_ligand_pose_qc: PoseBusters integration."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("posebusters")

from rdkit import Chem
from rdkit.Chem import AllChem

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_pose_qc import run_posebusters, split_complex


def _ligand_block(dx=0.0):
    mol = Chem.AddHs(Chem.MolFromSmiles("CC(=O)OC1=CC=CC=C1C(=O)O"))
    AllChem.EmbedMolecule(mol, randomSeed=7)
    AllChem.MMFFOptimizeMolecule(mol)
    conf = mol.GetConformer()
    lines = []
    for index, atom in enumerate(mol.GetAtoms()):
        pos = conf.GetAtomPosition(index)
        lines.append(
            f"HETATM{index + 1:5d} {atom.GetSymbol():<4s} LIG B   1    {pos.x + dx:8.3f}{pos.y:8.3f}{pos.z:8.3f}  1.00  0.00          {atom.GetSymbol():>2s}"
        )
    return lines


def _complex_form(dx):
    protein = [
        ("ALA", 1, 0.0, 0.0, 0.0, "CA"),
        ("GLY", 2, 3.8, 0.0, 0.0, "CA"),
        ("SER", 3, 7.6, 0.0, 0.0, "CA"),
    ]
    columns = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")
    encoders = {}
    rows = []
    for resname, number, x, y, z, name in protein:
        for label, value in (("resname", resname), ("chain", "A"), ("atom_name", name), ("element", "C")):
            encoders.setdefault(label, {})
            if value not in encoders[label]:
                encoders[label][value] = len(encoders[label])
        rows.append([x, y, z, number, "ALA", "A", "CA", "C"])
    from src.reader.readers._encoder import LabelEncoder

    field_encoders = {}
    for index, label in enumerate(("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        values = [("ALA" if label == "resname" else "A" if label == "chain" else "CA" if label == "atom_name" else "C")] * 3
        values += ["LIG"] if label == "resname" else (["B"] if label == "chain" else (["C"] if label == "atom_name" else ["C"]))
        encoder.fit_transform(values + ["O"] * 2)
        field_encoders[label] = encoder
    return rows, fields


def _form(dx):
    from src.reader import read_source
    import tempfile

    protein_lines = [
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
        "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00  0.00           C",
        "ATOM      3  CA  SER A   3       7.600   0.000   0.000  1.00  0.00           C",
    ]
    text = "\n".join(protein_lines + _ligand_block(dx)) + "\nEND\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "complex.pdb"
        path.write_text(text)
        return read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_split_complex_extracts_the_ligand():
    form = _form(12.0)
    protein_text, ligand_text = split_complex(form, "field", "LIG")
    assert ligand_text.count("HETATM") == 21
    assert "LIG" in ligand_text
    assert "LIG" not in protein_text


def test_far_ligand_passes_overlap_and_overlapping_ligand_fails():
    form = _form(12.0)
    protein_text, ligand_text = split_complex(form, "field", "LIG")
    far = run_posebusters(protein_text, ligand_text, config="dock")["checks"]
    assert far["volume_overlap_with_protein"] == 1.0
    assert far["bond_lengths"] == 1.0
    protein_text, ligand_text = split_complex(_form(0.0), "field", "LIG")
    near = run_posebusters(protein_text, ligand_text, config="dock")["checks"]
    assert near["volume_overlap_with_protein"] == 0.0


def test_run_writes_check_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form(12.0)
    run(ctx, [{"name": "structure_ligand_pose_qc", "inputs": ["pdb"], "params": {"output": "pose_qc", "ligand_resname": "LIG"}}])
    result = ctx["pose_qc"]
    assert result.dims == ["check", "statistic"]
    assert result.data.shape[0] == result.info["n_checks"] >= 15
    assert "bond_lengths" in result.labels["check"]
    assert result.info["config"] == "dock"


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form(12.0)
    with pytest.raises(StepError, match="no atom carries the residue name"):
        run(ctx, [{"name": "structure_ligand_pose_qc", "inputs": ["pdb"], "params": {"output": "pose_qc", "ligand_resname": "XYZ"}}])
