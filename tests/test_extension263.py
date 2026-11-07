"""Tests for LigandMPNN side-chain packing."""

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
packed = out / "packed"
packed.mkdir(parents=True, exist_ok=True)
(source, target) = os.environ["OPERON_PACK_SOURCE"], packed / (pdb.stem + "_packed.pdb")
target.write_text(Path(source).read_text())
Path(os.environ["OPERON_PACK_CAPTURE"]).write_text(json.dumps({"argv": sys.argv[1:]}))
"""


def _repo(tmp_path, source_pdb):
    repo = tmp_path / "LigandMPNN"
    weights = repo / "model_params"
    weights.mkdir(parents=True)
    (repo / "run.py").write_text(FAKE_RUNNER)
    (weights / "ligandmpnn_v_32_010_25.pt").write_text("stub")
    (weights / "ligandmpnn_sc_v_32_002_16.pt").write_text("stub")
    (tmp_path / "capture.json").write_text("{}")
    return repo, weights, source_pdb


def _params(tmp_path, repo, structure, **extra):
    params = {
        "structure_path": str(structure),
        "ligandmpnn_path": str(repo),
        "output": "packed",
    }
    params.update(extra)
    return params


def _run(tmp_path, params, repo, source, monkeypatch):
    capture = tmp_path / "capture.json"
    monkeypatch.setenv("OPERON_PACK_SOURCE", str(source))
    monkeypatch.setenv("OPERON_PACK_CAPTURE", str(capture))
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = params
    run(ctx, [{"name": "ligandmpnn_side_chain_packing", "inputs": [], "params": params}])
    return ctx["packed"], json.loads(capture.read_text())


def test_run_packs_the_backbone(tmp_path, monkeypatch) -> None:
    source = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"
    structure = tmp_path / "mini.pdb"
    structure.write_text(source.read_text()[:200000])
    repo, _weights, _ = _repo(tmp_path, structure)
    params = _params(tmp_path, repo, structure, number_of_packs_per_design=2)
    form, capture = _run(tmp_path, params, repo, source, monkeypatch)
    argv = capture["argv"]
    assert "--pack_side_chains" in argv and argv[argv.index("--pack_side_chains") + 1] == "1"
    assert argv[argv.index("--checkpoint_path_sc") + 1].endswith("ligandmpnn_sc_v_32_002_16.pt")
    assert argv[argv.index("--number_of_packs_per_design") + 1] == "2"
    assert form.dims == ["atom", "field"]
    assert "atom" in form.labels


def test_validation_errors(tmp_path, monkeypatch) -> None:
    source = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"
    structure = tmp_path / "mini.pdb"
    structure.write_text(source.read_text()[:200000])
    repo, weights, _ = _repo(tmp_path, structure)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = {"output": "packed"}

    with pytest.raises(StepError, match="is not a file"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": {"structure_path": str(tmp_path / "missing.pdb"), "output": "packed"},
                }
            ],
        )
    with pytest.raises(StepError, match="must name a .pdb"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": {"structure_path": str(repo / "run.py"), "output": "packed"},
                }
            ],
        )
    with pytest.raises(StepError, match="run.py was not found"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": {
                        "structure_path": str(structure),
                        "ligandmpnn_path": str(tmp_path / "nope"),
                        "output": "packed",
                    },
                }
            ],
        )
    (weights / "ligandmpnn_sc_v_32_002_16.pt").unlink()
    with pytest.raises(StepError, match="side-chain checkpoint"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": _params(tmp_path, repo, structure),
                }
            ],
        )
    (weights / "ligandmpnn_sc_v_32_002_16.pt").write_text("stub")
    with pytest.raises((StepError, ValueError), match="device"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": _params(tmp_path, repo, structure, device="tpu"),
                }
            ],
        )
    with pytest.raises((StepError, ValueError), match="model_type"):
        run(
            ctx,
            [
                {
                    "name": "ligandmpnn_side_chain_packing",
                    "inputs": [],
                    "params": _params(tmp_path, repo, structure, model_type="nope"),
                }
            ],
        )
