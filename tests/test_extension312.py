"""vina_dock_python: official Vina Python engine."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.vina_dock_python import ad4_type, dock, receptor_pdbqt, parse_ligand_box

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

LIGAND_PDBQT = """ROOT
ATOM      1  C   LIG B   1       0.000   0.000   0.000  1.00  0.00     0.000 A
ATOM      2  O   LIG B   1       1.400   0.000   0.000  1.00  0.00     0.000 OA
ATOM      3  C   LIG B   1      -1.400   0.000   0.000  1.00  0.00     0.000 A
ENDROOT
TORSDOF 0
"""


def test_ad4_type_and_receptor_conversion():
    assert ad4_type("C") == "A"
    assert ad4_type("O") == "OA"
    assert ad4_type("S") == "SA"
    assert ad4_type("Zn") == "Zn"
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    text = receptor_pdbqt(form)
    assert text.startswith("ATOM")
    assert "OA" in text
    assert text.count("\n") > 900
    first = text.splitlines()[0]
    assert first[77:79].strip() in {"A", "N", "OA", "SA", "C"}


def test_docking_against_the_real_engine(tmp_path):
    pytest.importorskip("vina")
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ligand = tmp_path / "ligand.pdbqt"
    ligand.write_text(LIGAND_PDBQT)
    result = dock(receptor_pdbqt(form), ligand, exhaustiveness=4, num_modes=3, seed=7, workdir=tmp_path / "run")
    energies = result["energies"]
    assert energies.shape[0] == 3
    assert energies[0, 0] < 0.0
    assert np.all(np.diff(energies[:, 0]) >= -1e-6)
    assert Path(result["pose_file"]).is_file()


def test_runner_round_trip(tmp_path):
    pytest.importorskip("vina")
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ligand = tmp_path / "ligand.pdbqt"
    ligand.write_text(LIGAND_PDBQT)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "vina_dock_python", "inputs": ["pdb"], "params": {"output": "docking", "ligand_path": str(ligand), "exhaustiveness": 4, "num_modes": 2}}])
    result = ctx["docking"]
    assert result.dims == ["pose", "statistic"]
    assert result.data.shape == (2, 5)
    assert result.info["best_affinity"] < 0.0


def test_errors(tmp_path):
    with pytest.raises(StepError, match="no element"):
        ad4_type("")
    with pytest.raises(StepError, match="is not a file"):
        parse_ligand_box(tmp_path / "missing.pdbqt")
    form = read_source(str(FIXTURES / "vhh_1mel.pdb"), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="must be a .pdbqt"):
        run(ctx, [{"name": "vina_dock_python", "inputs": ["pdb"], "params": {"output": "docking", "ligand_path": str(FIXTURES / "vhh_1mel.pdb")}}])
