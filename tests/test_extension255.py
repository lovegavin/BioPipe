"""Tests for the RDKit-based PDBQT ligand preparation operator."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("rdkit")

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.ligand_pdbqt_prepare import (
    LigandPdbqtPrepareStep,
    ad4_type,
    pdbqt_lines,
    prepare_molecule,
)


def test_prepare_molecule() -> None:
    molecule = prepare_molecule("CCO", seed=7)
    assert molecule.GetNumAtoms() == 9  # 3 heavy atoms + 6 hydrogens
    conformer = molecule.GetConformer()
    assert conformer.GetNumAtoms() == 9
    types = {ad4_type(atom) for atom in molecule.GetAtoms()}
    assert {"A", "OA", "H", "HD"} <= types

    lines = pdbqt_lines(molecule, name="EOH")
    assert lines[-1] == "TORSDOF 0"
    atom_lines = [line for line in lines if line.startswith("ATOM")]
    assert len(atom_lines) == 9
    charges = [float(line[70:77]) for line in atom_lines]
    assert any(abs(value) > 1e-3 for value in charges)


def test_run(tmp_path) -> None:
    target = tmp_path / "ligand.pdbqt"
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "ligand_pdbqt_prepare",
                "inputs": [],
                "params": {
                    "smiles": "c1ccccc1O",
                    "output_path": str(target),
                    "resname": "PHN",
                    "seed": 3,
                    "output": "lig",
                },
            }
        ],
    )
    out = ctx["lig"]
    assert out.dims == ["atom", "statistic"]
    assert out.data.shape[0] == 13  # phenol: 7 heavy + 6 hydrogens
    assert out.info["n_atoms"] == 13
    assert out.info["output_path"] == target.as_posix()
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert text.count("ATOM") == 13
    assert " PHN " in text


def test_errors(tmp_path) -> None:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="must not be empty"):
        run(ctx, [{"name": "ligand_pdbqt_prepare", "inputs": [], "params": {"smiles": ""}}])
    with pytest.raises(StepError, match="cannot be parsed"):
        run(ctx, [{"name": "ligand_pdbqt_prepare", "inputs": [], "params": {"smiles": "not-a-smiles"}}])
