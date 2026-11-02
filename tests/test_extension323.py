"""structure_ligand_redock_qc: PoseBusters redock wrapper."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("posebusters")
pytest.importorskip("rdkit")

from rdkit import Chem
from rdkit.Chem import AllChem

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_redock_qc import redock_rows, run_redock


def _ligand(path, shift=0.0):
    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    params = AllChem.ETKDGv3()
    params.randomSeed = 7
    AllChem.EmbedMolecule(mol, params)
    AllChem.MMFFOptimizeMolecule(mol)
    if shift:
        conf = mol.GetConformer()
        for index in range(mol.GetNumAtoms()):
            position = conf.GetAtomPosition(index)
            conf.SetAtomPosition(index, (position.x + shift, position.y, position.z))
    Chem.MolToMolFile(mol, str(path))


def _protein(path):
    lines = []
    for index in range(1, 40):
        x = index * 3.8
        for name, element in (("N", "N"), ("CA", "C"), ("C", "C"), ("O", "O")):
            lines.append(
                f"ATOM  {len(lines) + 1:5d} {name:<4s} ALA A{index:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00          {element:>2s}"
            )
    path.write_text("\n".join(lines) + "\n")


def test_redock_identical_and_shifted(tmp_path):
    _protein(tmp_path / "protein.pdb")
    _ligand(tmp_path / "crystal.sdf")
    _ligand(tmp_path / "pose.sdf", shift=3.0)
    report = run_redock(tmp_path / "protein.pdb", tmp_path / "crystal.sdf", tmp_path / "pose.sdf")
    metrics, summary = redock_rows(report, legend={})
    values = {metric["metric"]: metric["value"] for metric in metrics}
    assert values["rmsd"] == pytest.approx(3.0, abs=0.2)
    assert summary["rmsd_pass"] is False
    assert summary["n_checks"] > 5


def test_run_round_trip(tmp_path):
    _protein(tmp_path / "protein.pdb")
    _ligand(tmp_path / "crystal.sdf")
    _ligand(tmp_path / "pose.sdf", shift=3.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_ligand_redock_qc", "params": {
        "output": "redock",
        "complex_path": str(tmp_path / "protein.pdb"),
        "ligand_path": str(tmp_path / "crystal.sdf"),
        "pose_path": str(tmp_path / "pose.sdf"),
    }}])
    table = ctx["redock"]
    assert table.dims == ["metric", "statistic"]
    assert "rmsd" in table.labels["metric"]
    assert table.info["rmsd_pass"] is False
    assert table.info["n_failed"] >= 1


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        run_redock(tmp_path / "missing.pdb", tmp_path / "x.sdf", tmp_path / "y.sdf")
