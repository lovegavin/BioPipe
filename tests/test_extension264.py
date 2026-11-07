"""Tests for ProteinMPNN bias matrix."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

FAKE_RUNNER = """import json
import os
import sys
from pathlib import Path

out = Path(sys.argv[sys.argv.index("--out_folder") + 1])
pdb = Path(sys.argv[sys.argv.index("--pdb_path") + 1])
(out / "seqs").mkdir(parents=True, exist_ok=True)
header = ">T=" + pdb.stem + ", sample=1, score=1.1, global_score=1.2, seq_recovery=0.5"
(out / "seqs" / (pdb.stem + ".fa")).write_text(chr(10).join([header, "AAAA", ""]))
bias = ""
if "--bias_by_res_jsonl" in sys.argv:
    bias = Path(sys.argv[sys.argv.index("--bias_by_res_jsonl") + 1]).read_text()
Path(os.environ["OPERON_BIAS_CAPTURE"]).write_text(json.dumps({"argv": sys.argv[1:], "bias": bias}))
"""


def _repo(tmp_path):
    repo = tmp_path / "proteinmpnn"
    weights = repo / "vanilla_model_weights"
    weights.mkdir(parents=True)
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    (weights / "v_48_020.pt").write_text("stub")
    return repo


def _structure(path: Path) -> Path:
    lines = []
    for serial, resname in enumerate(("ALA", "GLY", "SER"), start=1):
        lines.append(
            "ATOM  "
            f"{serial:5d} CA   {resname} A{serial:4d}    "
            f"{serial * 3.8:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 50.00           C"
        )
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")
    return path


def test_bias_matrix_hand_case() -> None:
    from src.task.step.steps.proteinmpnn_bias_matrix import bias_matrix

    matrix = bias_matrix(
        {"A": [1, 2]},
        {"A": [2]},
        favor="W",
        avoid="A",
        strength=2.0,
    )
    assert len(matrix["A"]) == 2
    assert matrix["A"][0] == [0.0] * 21
    assert matrix["A"][1][18] == 2.0  # W
    assert matrix["A"][1][0] == -2.0  # A
    assert sum(1 for value in matrix["A"][1] if value != 0.0) == 2


def test_bias_matrix_rejects_unknown_residues() -> None:
    from src.task.step.steps.proteinmpnn_bias_matrix import bias_matrix

    with pytest.raises(StepError, match="not a standard amino acid"):
        bias_matrix({"A": [1]}, {"A": [1]}, favor="Z", avoid="", strength=1.0)


def test_run_bias_design(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path / "mini.pdb")
    capture = tmp_path / "capture.json"
    monkeypatch.setenv("OPERON_BIAS_CAPTURE", str(capture))
    params = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "positions": "A:2",
        "num_seq_per_target": 1,
        "output": "designs",
    }
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = params
    run(ctx, [{"name": "proteinmpnn_bias_matrix", "inputs": [], "params": params}])
    out = ctx["designs"]
    captured = json.loads(capture.read_text())
    assert out.data.shape == (1, 2)
    assert out.info["sequences"] == ["AAAA"]
    assert out.info["favor"] == "WYFH"
    assert out.info["bias_positions"] == {"A": [2]}
    payload = json.loads(captured["bias"])
    block = payload["mini"]["A"]
    assert len(block) == 3
    assert len(block[1]) == 21
    assert block[1][18] == 1.0  # W favored by default
    assert block[1][0] == 0.0  # A not avoided


def test_validation_errors(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path / "mini.pdb")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = {"output": "designs"}
    with pytest.raises(StepError, match="is not a file"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_bias_matrix",
                    "inputs": [],
                    "params": {"structure_path": str(tmp_path / "nope.pdb"), "positions": "A:1"},
                }
            ],
        )
    with pytest.raises(StepError, match="residue 9 is not an author residue number"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_bias_matrix",
                    "inputs": [],
                    "params": {
                        "structure_path": str(structure),
                        "proteinmpnn_path": str(repo),
                        "positions": "A:9",
                    },
                }
            ],
        )
    with pytest.raises((StepError, ValueError), match="strength"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_bias_matrix",
                    "inputs": [],
                    "params": {
                        "structure_path": str(structure),
                        "proteinmpnn_path": str(repo),
                        "positions": "A:1",
                        "strength": 0.0,
                    },
                }
            ],
        )
