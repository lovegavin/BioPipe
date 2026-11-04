"""Tests for the interface-restricted ProteinMPNN score operator."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.reader import read_source
from src.task.step.steps.proteinmpnn_masked_interface_score import (
    ProteinmpnnMaskedInterfaceScoreStep,
    load_scores,
    sequential_index,
    sequential_indices,
    summary,
)


def _line(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float, element: str) -> str:
    return (
        f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}\n"
    )


def _complex_pdb(path: Path) -> Path:
    text = (
        _line(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, "N")
        + _line(2, "CA", "ALA", "A", 1, 1.5, 0.0, 0.0, "C")
        + _line(3, "N", "GLY", "A", 2, 4.0, 0.0, 0.0, "N")
        + _line(4, "N", "SER", "A", 3, 30.0, 0.0, 0.0, "N")
        + _line(5, "N", "THR", "B", 1, 0.0, 0.0, 2.0, "N")
    )
    path.write_text(text, encoding="utf-8")
    return path


FAKE_RUNNER = r'''
import pathlib, sys
import numpy as np

args = sys.argv[1:]

def value(flag):
    return args[args.index(flag) + 1]

pdb = pathlib.Path(value("--pdb_path"))
folder = pathlib.Path(value("--out_folder")) / "conditional_probs_only"
folder.mkdir(parents=True, exist_ok=True)
import os
text = os.environ.get("FAKE_SCORES", "0.5,1.0,2.0,3.0")
nll = [float(item) for item in text.split(",")]
log_p = np.full((1, len(nll), 21), -9.0, dtype=np.float64)
native = np.arange(len(nll), dtype=int)
for index, value_nll in enumerate(nll):
    log_p[0, index, native[index]] = -value_nll
np.savez(folder / (pdb.stem + ".npz"), log_p=log_p, S=native)
'''


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"stub")
    return repo


def _params(repo: Path, structure: Path, **overrides) -> dict:
    params = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "binder_chains": "A",
        "target_chains": "B",
        "cutoff": 4.5,
        "python_executable": sys.executable,
        "output": "iface",
    }
    params.update(overrides)
    return params


def test_helpers(tmp_path) -> None:
    assert sequential_indices({"A": [1, 2], "B": [1]}) == {"A:1": 1, "A:2": 2, "B:1": 3}
    assert sequential_index({"A": [1, 2], "B": [1]}, "B:THR:1") == 3
    with pytest.raises(StepError, match="absent from the structure"):
        sequential_index({"A": [1]}, "Z:ALA:1")
    with pytest.raises(StepError, match="not an author residue number"):
        sequential_index({"A": [1]}, "A:ALA:7")

    npz = tmp_path / "scores.npz"
    log_p = np.full((1, 4, 21), -9.0, dtype=np.float64)
    native = np.asarray([0, 1, 2, 3])
    for index, value_nll in enumerate((1.0, 2.0, 3.0, 4.0)):
        log_p[0, index, index] = -value_nll
    np.savez(npz, log_p=log_p, S=native)
    scores, sequence = load_scores(npz)
    assert sequence == "ACDE"
    assert summary(scores, [1, 3], "interface") == (2.0, 1.0, 3.0, 2)
    with pytest.raises(StepError, match="no residue falls"):
        summary(scores, [], "interface")


def test_run(tmp_path) -> None:
    structure = _complex_pdb(tmp_path / "complex.pdb")
    form = read_source(structure, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "proteinmpnn_masked_interface_score", "inputs": ["pdb"], "params": _params(_repo(tmp_path), structure)}])
    out = ctx["iface"]
    assert out.dims == ["region", "statistic"]
    rows = {name: out.data[position] for name, position in out.labels["region"].items()}
    assert rows["interface"][3] == pytest.approx(3.0)
    assert rows["other"][0] == pytest.approx(2.0, abs=1e-6)
    assert out.info["n_interface_residues"] == 3
    assert out.info["n_contact_pairs"] > 0


def test_run_errors(tmp_path) -> None:
    structure = _complex_pdb(tmp_path / "complex.pdb")
    form = read_source(structure, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    repo = _repo(tmp_path)

    def _ctx() -> Context:
        ctx = Context(str(tmp_path / "task"), {"params": {}})
        ctx["pdb"] = form
        return ctx

    with pytest.raises(StepError, match="structure_path"):
        run(_ctx(), [{"name": "proteinmpnn_masked_interface_score", "inputs": ["pdb"], "params": _params(repo, tmp_path / "missing.pdb")}])
    with pytest.raises(StepError, match="does not look like"):
        run(_ctx(), [{"name": "proteinmpnn_masked_interface_score", "inputs": ["pdb"], "params": _params(tmp_path / "nope", structure)}])
    with pytest.raises(StepError, match="chain"):
        run(_ctx(), [{"name": "proteinmpnn_masked_interface_score", "inputs": ["pdb"], "params": _params(repo, structure, target_chains="Z")}])
