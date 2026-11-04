"""structure_pdbqt_flexible_receptor: rigid + flex pair accepted by Vina."""

from pathlib import Path

import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_pdbqt_flexible_receptor import (
    build_pair,
    flexible_residues,
    residue_groups,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _form():
    return read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_candidates_have_side_chains():
    form = _form()
    candidates = flexible_residues(form, "field")
    assert len(candidates) > 50
    assert all(":" in f"{chain}:{number}" for chain, number in candidates)


def test_pair_contains_begin_res_blocks():
    form = _form()
    candidates = flexible_residues(form, "field", "A:2")
    selected = candidates[:1]
    result = build_pair(form, "field", [("A", 2)])
    assert result["flex"].startswith("BEGIN_RES")
    assert "END_RES" in result["flex"]
    assert result["rigid"].startswith("ATOM")
    assert "ROOT" in result["flex"] and "ENDROOT" in result["flex"]
    assert result["n_torsions"] >= 1


def test_vina_accepts_the_pair(tmp_path):
    pytest.importorskip("vina")
    from vina import Vina

    from src.task.step.steps.ligand_pdbqt_flexible import prepare_flexible

    form = _form()
    result = build_pair(form, "field", [("A", 2)])
    rigid = tmp_path / "rigid.pdbqt"
    flex = tmp_path / "flex.pdbqt"
    rigid.write_text(result["rigid"])
    flex.write_text(result["flex"])
    ligand = tmp_path / "ligand.pdbqt"
    ligand.write_text("\n".join(prepare_flexible("CCO")["lines"]) + "\n")
    engine = Vina(sf_name="vina", cpu=1, seed=3, verbosity=0)
    engine.set_receptor(str(rigid), str(flex))
    engine.set_ligand_from_file(str(ligand))
    engine.compute_vina_maps(center=[0.0, 0.0, 0.0], box_size=[20.0, 20.0, 20.0])
    engine.dock(exhaustiveness=2, n_poses=1)
    assert engine.energies(n_poses=1)[0][0] < 0.0


def test_run_writes_files(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    rigid = tmp_path / "rigid.pdbqt"
    flex = tmp_path / "flex.pdbqt"
    run(ctx, [{"name": "structure_pdbqt_flexible_receptor", "inputs": ["pdb"], "params": {"output": "receptor", "flexible_residues": "A:2", "output_path": str(rigid), "flex_output_path": str(flex)}}])
    result = ctx["receptor"]
    assert result.info["flexible_residues"] == ["A:2"]
    assert rigid.is_file() and flex.is_file()
    assert result.data.shape == (1, 3)


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not of the form"):
        flexible_residues(_form(), "field", "A45")
    with pytest.raises(StepError, match="is not in the structure"):
        flexible_residues(_form(), "field", "Z:999")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    with pytest.raises(StepError, match="must end with .pdbqt"):
        run(ctx, [{"name": "structure_pdbqt_flexible_receptor", "inputs": ["pdb"], "params": {"output": "receptor", "flexible_residues": "A:2", "output_path": str(tmp_path / "x.txt")}}])
