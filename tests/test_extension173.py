"""Runner-level contract checks for the v1.32 operators."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run

PAYLOAD = r'''
import sys
from pathlib import Path

argv = sys.argv[1:]
out = Path(argv[argv.index("--out_folder") + 1])
pdb = Path(argv[argv.index("--pdb_path") + 1])
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
lines = [f">{pdb.stem}, T=0.10, num_res=6", "ACDEFG"]
for index, sequence in enumerate(["ACDEFG", "ACDEFY", "ACDEAA", "ACDEFG"], start=1):
    lines.append(f">{pdb.stem}, id={index}, T=0.10, sample={index}, score=1.0, seq_recovery=0.5")
    lines.append(sequence)
(seqs / f"{pdb.stem}.fa").write_text("\n".join(lines) + "\n", encoding="utf-8")
'''


def _atom(serial, name, resname, chain, number, x, y, z, element):
    return (
        f"{'ATOM':<6}{serial:>5} {name:<4} {resname:>3} "
        f"{chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{0.00:>6.2f}          {element:>2}"
    )


def _hexagon(start, resname, chain, number, center=(0.0, 0.0, 0.0)):
    names = ["CG", "CD1", "CE1", "CZ", "CE2", "CD2"]
    rows = []
    for index, name in enumerate(names):
        theta = math.radians(60.0 * index)
        rows.append(
            _atom(
                start + index,
                name,
                resname,
                chain,
                number,
                center[0] + 1.4 * math.cos(theta),
                center[1] + 1.4 * math.sin(theta),
                center[2],
                "C",
            )
        )
    return rows


def _structure_pdb(tmp_path: Path) -> Path:
    lines = [
        _atom(1, "N", "ALA", "A", 1, 0.0, 0.0, 1.6, "N"),
        _atom(2, "CA", "ALA", "A", 1, 0.0, 0.0, 2.0, "C"),
        _atom(3, "C", "ALA", "A", 1, 0.0, 0.0, 2.4, "C"),
        _atom(4, "O", "ALA", "A", 1, 0.0, 0.0, 3.2, "O"),
        _atom(5, "N", "PHE", "A", 2, 0.0, 0.0, 2.0, "N"),
    ]
    lines.extend(_hexagon(9, "PHE", "A", 2, (0.0, 0.0, 4.5)))
    lines.extend(_hexagon(20, "TYR", "A", 6, (20.0, 0.0, 0.0)))
    path = tmp_path / "structure.pdb"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _read(path: Path):
    return read_source(
        path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _context(tmp_path: Path) -> Context:
    return Context(tmp_path / "task", {"params": {}})


def _export(ctx: Context, step_name: str) -> dict:
    path = ctx.out_dir / "steps" / f"01_{step_name}.json"
    assert path.is_file(), f"missing export {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_structure_interactions_through_runner(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    ctx["pdb"] = _read(_structure_pdb(tmp_path))
    run(
        ctx,
        [
            {
                "name": "structure_amide_pi_bonds",
                "inputs": ["pdb"],
                "params": {"output": "amide_pi"},
            }
        ],
    )
    form = ctx["amide_pi"]
    assert form.data.shape == (1, 3)
    payload = _export(ctx, "structure_amide_pi_bonds")
    assert payload["n_bonds"] == 1
    run(
        ctx,
        [
            {
                "name": "structure_aromatic_stacking",
                "inputs": ["pdb"],
                "params": {"output": "stacking"},
            }
        ],
    )
    assert ctx["stacking"].data.shape[1] == 5


def test_conformer_cluster_through_runner(tmp_path: Path) -> None:
    ctx = _context(tmp_path)
    run(
        ctx,
        [
            {
                "name": "rdkit_conformer_cluster",
                "inputs": [],
                "params": {"smiles": "CCCCCC", "num_conformers": 4, "output": "clusters"},
            }
        ],
    )
    out = ctx["clusters"]
    assert out.data.shape[0] == 1
    assert out.data.sum() == out.info["molecules"][0]["n_conformers"]
    payload = _export(ctx, "rdkit_conformer_cluster")
    assert payload["n_molecules"] == 1


def test_design_profile_through_runner(tmp_path: Path) -> None:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("fake", encoding="utf-8")
    (repo / "protein_mpnn_run.py").write_text(PAYLOAD, encoding="utf-8")
    structure = tmp_path / "mini.pdb"
    structure.write_text("ATOM\n", encoding="utf-8")
    ctx = _context(tmp_path)
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_design_profile",
                "inputs": [],
                "params": {
                    "structure_path": str(structure),
                    "proteinmpnn_path": str(repo),
                    "weights_path": str(repo / "vanilla_model_weights"),
                    "num_seq_per_target": 4,
                    "python_executable": sys.executable,
                    "output": "profile",
                },
            }
        ],
    )
    form = ctx["profile"]
    assert form.data.shape == (6, 20)
    assert np.allclose(form.data.sum(axis=1), 1.0)
    payload = _export(ctx, "proteinmpnn_design_profile")
    assert payload["positions"] == 6
