"""Tests for the batch docking operator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.vina_dock_batch import split_paths, unique_labels

FAKE_VINA = """import sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out") + 1])
ligand = Path(args[args.index("--ligand") + 1])
out.write_text("MODEL\\nATOM      1  C   LIG A   1       0.000   0.000   0.000  1.00  0.00    +0.000 A \\nENDMDL\\n")
if ligand.stem.startswith("bad"):
    print("no binding mode", file=sys.stderr)
    sys.exit(0)
print("mode |   affinity | dist from best mode")
print("     | (kcal/mol) | rmsd l.b.| rmsd u.b.")
print("   1        -7.5      0.000      0.000")
print("   2        -6.0      1.000      2.000")
"""


def _pdbqt(path: Path, x: float, y: float = 0.0, z: float = 0.0, lines: int = 2) -> Path:
    rows = []
    for serial in range(1, lines + 1):
        ox, oy, oz = x + serial, y, z
        rows.append(
            "ATOM  {serial:5d}  C   LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}"
            "  1.00  0.00    +0.000 A ".format(serial=serial, x=ox, y=oy, z=oz)
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _script(tmp_path: Path) -> Path:
    path = tmp_path / "fake_vina.py"
    path.write_text(FAKE_VINA, encoding="utf-8")
    return path


def test_split_paths_and_labels() -> None:
    assert split_paths("a.pdbqt, b.pdbqt;c.pdbqt\nd.pdbqt") == [
        "a.pdbqt",
        "b.pdbqt",
        "c.pdbqt",
        "d.pdbqt",
    ]
    labels = unique_labels([Path("lig.pdbqt"), Path("lig.pdbqt"), Path("other.pdbqt")])
    assert labels == ["lig", "lig#2", "other"]


def test_run_docks_two_ligands(tmp_path) -> None:
    receptor = _pdbqt(tmp_path / "receptor.pdbqt", 0.0, lines=4)
    ligand_a = _pdbqt(tmp_path / "lig_a.pdbqt", 0.0)
    ligand_b = _pdbqt(tmp_path / "lig_b.pdbqt", 10.0)
    script = _script(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    params = {
        "receptor_path": str(receptor),
        "ligand_paths": f"{ligand_a}, {ligand_b}",
        "vina_path": str(script),
        "output": "results",
    }
    ctx.step_params = params
    run(ctx, [{"name": "vina_dock_batch", "inputs": [], "params": params}])
    out = ctx["results"]
    assert out.data.shape == (2, 4)
    assert list(out.labels["ligand"]) == ["lig_a", "lig_b"]
    assert out.data[:, 0].tolist() == pytest.approx([-7.5, -7.5])
    assert out.data[:, 3].tolist() == pytest.approx([2.0, 2.0])
    assert out.info["best_ligand"] in {"lig_a", "lig_b"}
    assert Path(out.info["poses"]["lig_a"]).is_file()
    capture_center = out.info["center"]
    assert capture_center == pytest.approx([6.5, 0.0, 0.0])


def test_explicit_center_is_used(tmp_path) -> None:
    receptor = _pdbqt(tmp_path / "receptor.pdbqt", 0.0, lines=2)
    ligand = _pdbqt(tmp_path / "lig.pdbqt", 0.0)
    script = _script(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    params = {
        "receptor_path": str(receptor),
        "ligand_paths": str(ligand),
        "vina_path": str(script),
        "center_x": 1.0,
        "center_y": 2.0,
        "center_z": 3.0,
        "output": "results",
    }
    ctx.step_params = params
    run(ctx, [{"name": "vina_dock_batch", "inputs": [], "params": params}])
    assert ctx["results"].info["center"] == [1.0, 2.0, 3.0]


def test_errors(tmp_path) -> None:
    receptor = _pdbqt(tmp_path / "receptor.pdbqt", 0.0)
    ligand = _pdbqt(tmp_path / "lig.pdbqt", 0.0)
    script = _script(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="receptor_path is required"):
        run(
            ctx,
            [{"name": "vina_dock_batch", "inputs": [], "params": {"ligand_paths": str(ligand)}}],
        )
    ligand.with_suffix(".mol2").write_text("")
    with pytest.raises(StepError, match="is not a .pdbqt file"):
        run(
            ctx,
            [
                {
                    "name": "vina_dock_batch",
                    "inputs": [],
                    "params": {
                        "receptor_path": str(receptor),
                        "ligand_paths": str(ligand.with_suffix(".mol2")),
                    },
                }
            ],
        )
    with pytest.raises(StepError, match="was not found on PATH"):
        run(
            ctx,
            [
                {
                    "name": "vina_dock_batch",
                    "inputs": [],
                    "params": {
                        "receptor_path": str(receptor),
                        "ligand_paths": str(ligand),
                        "vina_path": "definitely-not-vina",
                        "timeout_seconds": 5,
                        "output": "results",
                    },
                }
            ],
        )
    with pytest.raises(StepError, match="ligand_paths must list at least one"):
        run(
            ctx,
            [
                {
                    "name": "vina_dock_batch",
                    "inputs": [],
                    "params": {"receptor_path": str(receptor), "ligand_paths": ""},
                }
            ],
        )
    assert script.is_file()
