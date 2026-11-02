"""ligand_pdbqt_flexible: torsion tree against RDKit and Vina."""

from pathlib import Path

import pytest

pytest.importorskip("rdkit")

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.ligand_pdbqt_flexible import prepare_flexible, rotatable_bonds, torsion_tree


def test_torsion_counts_match_rdkit():
    cases = {"CCO ethanol": 0, "CC(=O)OC1=CC=CC=C1C(=O)O aspirin": 3, "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O ibuprofen": 4}
    for label, expected in cases.items():
        smiles = label.split()[0]
        result = prepare_flexible(smiles)
        assert result["torsions"] == expected, label


def test_tree_has_balanced_branches():
    result = prepare_flexible("CC(=O)OC1=CC=CC=C1C(=O)O")
    lines = result["lines"]
    assert lines[0] == "ROOT"
    assert "ENDROOT" in lines
    branches = [line for line in lines if line.startswith("BRANCH")]
    ends = [line for line in lines if line.startswith("ENDBRANCH")]
    assert len(branches) == len(ends) == result["torsions"]
    assert f"TORSDOF {result['torsions']}" in lines


def test_ethanol_has_no_branches():
    lines = torsion_tree(prepare_flexible("CCO")["molecule"])
    assert not any(line.startswith("BRANCH") for line in lines)
    assert "TORSDOF 0" in lines


def test_run_writes_pdbqt_and_table(tmp_path):
    target = tmp_path / "ligand.pdbqt"
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "ligand_pdbqt_flexible", "params": {"output": "ligand", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "output_path": str(target)}}])
    result = ctx["ligand"]
    assert result.info["n_torsions"] == 3
    assert target.is_file()
    text = target.read_text()
    assert text.startswith("ROOT")
    assert "ENDROOT" in text
    assert "TORSDOF 3" in text


def test_docks_with_vina(tmp_path):
    pytest.importorskip("vina")
    from src.reader import read_source
    from src.task.step.steps.vina_dock_python import dock, receptor_pdbqt

    ligand = tmp_path / "ligand.pdbqt"
    ligand.write_text("\n".join(prepare_flexible("CC(=O)OC1=CC=CC=C1C(=O)O")["lines"]) + "\n")
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"
    form = read_source(str(fixture), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    result = dock(receptor_pdbqt(form), ligand, exhaustiveness=4, num_modes=3, seed=5, workdir=tmp_path / "run")
    assert result["energies"].shape[0] == 3
    assert result["energies"][0, 0] < 0.0


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="smiles is required"):
        run(ctx, [{"name": "ligand_pdbqt_flexible", "params": {"output": "ligand"}}])
    with pytest.raises(StepError, match="must end with .pdbqt"):
        run(ctx, [{"name": "ligand_pdbqt_flexible", "params": {"output": "ligand", "smiles": "CCO", "output_path": str(tmp_path / "x.txt")}}])
    with pytest.raises(StepError, match="cannot be parsed"):
        prepare_flexible("not-a-smiles")
