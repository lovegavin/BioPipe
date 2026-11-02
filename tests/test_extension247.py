"""Tests for the AutoDock Vina docking operator."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.vina_dock import (
    VinaDockStep,
    docking_command,
    element_of,
    ligand_centroid,
    parse_poses,
    parse_vina_log,
)

def _pdbqt_line(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float, charge: float, atom_type: str) -> str:
    return (
        f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}    {charge:7.3f} {atom_type:<2s}\n"
    )


def _ligand(offset: float = 0.0) -> str:
    return (
        "MODEL 1\n"
        + _pdbqt_line(1, "C1", "LIG", "A", 1, 1.0 + offset, 2.0, 3.0, -0.1, "A")
        + _pdbqt_line(2, "O1", "LIG", "A", 1, 2.0 + offset, 2.0, 3.0, -0.3, "OA")
        + "ENDMDL\n"
        "MODEL 2\n"
        + _pdbqt_line(1, "C1", "LIG", "A", 1, 1.5 + offset, 2.0, 3.0, -0.1, "A")
        + _pdbqt_line(2, "O1", "LIG", "A", 1, 2.5 + offset, 2.0, 3.0, -0.3, "OA")
        + "ENDMDL\n"
    )


RECEPTOR = (
    _pdbqt_line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, 0.0, "N")
    + _pdbqt_line(2, "CA", "ALA", "A", 1, 1.5, 0.0, 0.0, 0.0, "C")
)

LIGAND = _ligand()

LIGAND = """MODEL 1
ATOM      1  C1  LIG A   1       1.000   2.000   3.000  1.00  0.00    -0.100 A
ATOM      2  O1  LIG A   1       2.000   2.000   3.000  1.00  0.00    -0.300 OA
ENDMDL
MODEL 2
ATOM      1  C1  LIG A   1       1.500   2.000   3.000  1.00  0.00    -0.100 A
ATOM      2  O1  LIG A   1       2.500   2.000   3.000  1.00  0.00    -0.300 OA
ENDMDL
"""

LOG = """mode |   affinity | dist from best mode
     | (kcal/mol) | rmsd l.b.| rmsd u.b.
-----+------------+----------+----------
   1       -7.5      0.000      0.000
   2       -7.1      1.234      2.345
"""


def _fake_vina(tmp_path) -> Path:
    binary = tmp_path / "vina.py"
    body = [
        "import pathlib, sys",
        "args = sys.argv[1:]",
        "def value(flag):",
        "    return args[args.index(flag) + 1]",
        f"poses = {_ligand()!r}",
        f"log = {LOG!r}",
        "pathlib.Path(value('--out')).write_text(poses)",
        "pathlib.Path(value('--log')).write_text(log)",
    ]
    binary.write_text("\n".join(body) + "\n", encoding="utf-8")
    return binary


def test_element_of() -> None:
    assert element_of("A") == "C"
    assert element_of("OA") == "O"
    assert element_of("NA") == "N"
    assert element_of("HD") == "H"
    assert element_of("", "CA") == "CA"


def test_parse_vina_log() -> None:
    parsed = parse_vina_log(LOG)
    assert parsed["affinities"] == pytest.approx([-7.5, -7.1])
    assert parsed["best_affinity"] == pytest.approx(-7.5)
    assert parsed["rmsd_lb"] == pytest.approx([0.0, 1.234])
    assert parsed["rmsd_ub"] == pytest.approx([0.0, 2.345])
    assert np.isnan(parse_vina_log("")["best_affinity"])


def test_parse_poses(tmp_path) -> None:
    path = tmp_path / "poses.pdbqt"
    path.write_text(LIGAND, encoding="utf-8")
    poses = parse_poses(path)
    assert len(poses) == 2
    assert poses[0]["n_atoms"] == 2
    assert poses[1]["coordinates"][0].tolist() == [1.5, 2.0, 3.0]
    assert poses[0]["atoms"][0]["charge"] == pytest.approx(-0.1)
    assert poses[0]["elements"] == ["C", "O"]
    assert poses[0]["index"] == 1
    centroid = ligand_centroid(path)
    assert centroid == pytest.approx((1.5, 2.0, 3.0))


def test_parse_poses_errors(tmp_path) -> None:
    missing = tmp_path / "none.pdbqt"
    missing.write_text("nothing here\n", encoding="utf-8")
    with pytest.raises(StepError, match="holds no MODEL blocks"):
        parse_poses(missing)

    broken = tmp_path / "broken.pdbqt"
    broken.write_text("MODEL 1\nATOM  x\nENDMDL\n", encoding="utf-8")
    with pytest.raises(StepError, match="malformed pose line"):
        parse_poses(broken)


def test_docking_command(tmp_path) -> None:
    command = docking_command(
        {"size_x": 22, "num_modes": 5, "exhaustiveness": 4, "seed": 7},
        "vina",
        tmp_path / "r.pdbqt",
        tmp_path / "l.pdbqt",
        tmp_path / "out.pdbqt",
        (1.0, 2.0, 3.0),
    )
    assert command[0] == "vina"
    assert command[command.index("--center_x") + 1] == "1.000"
    assert command[command.index("--size_x") + 1] == "22.000"
    assert command[command.index("--num_modes") + 1] == "5"
    assert command[command.index("--exhaustiveness") + 1] == "4"
    assert command[command.index("--seed") + 1] == "7"


def _write_inputs(tmp_path) -> tuple[Path, Path]:
    receptor = tmp_path / "receptor.pdbqt"
    ligand = tmp_path / "ligand.pdbqt"
    receptor.write_text(RECEPTOR, encoding="utf-8")
    ligand.write_text(LIGAND, encoding="utf-8")
    return receptor, ligand


def test_run(tmp_path) -> None:
    receptor, ligand = _write_inputs(tmp_path)
    binary = _fake_vina(tmp_path)
    params = {
        "output": "poses",
        "receptor_path": str(receptor),
        "ligand_path": str(ligand),
        "vina_path": str(binary),
    }
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "vina_dock", "inputs": [], "params": params}])
    form = ctx["poses"]
    assert form.dims == ["pose", "atom", "field"]
    assert form.data.shape == (2, 2, 5)
    assert form.info["n_poses"] == 2
    assert form.info["best_affinity"] == pytest.approx(-7.5)
    assert form.data[0, 0, 4] == pytest.approx(6.0)


def test_run_errors(tmp_path) -> None:
    receptor, ligand = _write_inputs(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    binary = _fake_vina(tmp_path)
    with pytest.raises(StepError, match="not a .pdbqt file"):
        plain = tmp_path / "receptor.pdb"
        plain.write_text(RECEPTOR, encoding="utf-8")
        run(ctx, [{"name": "vina_dock", "inputs": [], "params": {"receptor_path": str(plain), "ligand_path": str(ligand), "vina_path": str(binary)}}])
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "vina_dock", "inputs": [], "params": {"receptor_path": str(receptor), "ligand_path": str(tmp_path / "none.pdbqt"), "vina_path": str(binary)}}])
    with pytest.raises(StepError, match="was not found on PATH"):
        run(ctx, [{"name": "vina_dock", "inputs": [], "params": {"receptor_path": str(receptor), "ligand_path": str(ligand), "vina_path": "definitely-not-vina"}}])


def test_definition() -> None:
    assert VinaDockStep.definition["inputs_arity"] == 0
    assert VinaDockStep.definition["category"] == "Machine Learning"
    assert sys.executable
