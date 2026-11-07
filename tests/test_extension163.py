"""Runner-level contract checks and real-oracle checks for the v1.30.0 operators."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_extension159 import _fasta, _repo, _structure
from test_extension161 import _pdb

from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.proteinmpnn_score import ProteinmpnnScoreStep

REAL_REPO = Path(os.environ.get("OPERON_PROTEINMPNN_PATH", "/home/gavin/tools/ProteinMPNN"))
FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


def _context(tmp_path, forms):
    ctx = Context(tmp_path / "task", {"params": {}})
    for name, form in forms.items():
        ctx[name] = form
    return ctx


def test_runner_contracts(tmp_path) -> None:
    complex_form = read_source(
        _pdb(tmp_path), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )
    ctx = _context(
        tmp_path,
        {"seq": encode_sequences(["AANGSV", "GGNNST"], "sequence", "position", "protein"), "complex": complex_form},
    )
    run(
        ctx,
        [
            {
                "name": "prosite_scan",
                "inputs": ["seq"],
                "params": {"patterns": "N-{P}-[ST] glyco", "output": "motifs"},
            },
            {
                "name": "rdkit_mcs_cluster",
                "inputs": [],
                "params": {"smiles": "c1ccccc1 benzene\nCc1ccccc1 toluene", "output": "clusters"},
            },
            {
                "name": "interface_hbond_network",
                "inputs": ["complex"],
                "params": {"binder_chains": "A", "target_chains": "B", "output": "bonds"},
            },
        ],
    )
    assert ctx["motifs"].data.shape == (1, 4)
    assert ctx["clusters"].data.shape == (2, 1)
    assert ctx["bonds"].data.shape == (1, 2)
    exports = sorted((tmp_path / "task" / "output" / "steps").glob("*.json"))
    assert len(exports) == 3


def test_runner_contract_ensemble(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setenv("FAKE_MPNN_LOG", str(tmp_path / "captured.json"))
    ctx = _context(tmp_path, {})
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_ensemble_score",
                "inputs": [],
                "params": {
                    "structure_path": str(_structure(tmp_path)),
                    "fasta_path": str(_fasta(tmp_path)),
                    "proteinmpnn_path": str(repo),
                    "python_executable": sys.executable,
                    "models": "v_48_002,v_48_010",
                    "device": "cpu",
                    "output": "ensemble",
                },
            }
        ],
    )
    assert ctx["ensemble"].data.shape == (2, 2)


@pytest.mark.skipif(
    not os.environ.get("OPERON_RUN_PROTEINMPNN") or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="set OPERON_RUN_PROTEINMPNN=1 with a local ProteinMPNN checkout",
)
def test_real_ensemble_matches_single_model(tmp_path) -> None:
    fasta = tmp_path / "native.fasta"
    fasta.write_text(">native\nSRALRYYYVKNIIKKV\n", encoding="utf-8")
    ctx = _context(tmp_path, {})
    models = "v_48_002,v_48_020"
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_ensemble_score",
                "inputs": [],
                "params": {
                    "structure_path": str(FIXTURE),
                    "fasta_path": str(fasta),
                    "proteinmpnn_path": str(REAL_REPO),
                    "models": models,
                    "chains": "C",
                    "device": "cpu",
                    "output": "ensemble",
                },
            }
        ],
    )
    ensemble = ctx["ensemble"]
    assert list(ensemble.labels["model"]) == models.split(",")
    matrix = np.asarray(ensemble.data)
    for position, model in enumerate(models.split(",")):
        single = ProteinmpnnScoreStep()
        single_ctx = _context(tmp_path / model, {})
        single_ctx.step_params = {
            "structure_path": str(FIXTURE),
            "fasta_path": str(fasta),
            "proteinmpnn_path": str(REAL_REPO),
            "model_name": model,
            "chains": "C",
            "device": "cpu",
            "output": "score",
        }
        single.run(single_ctx, [])
        expected = float(np.asarray(single_ctx["score"].data)[0, 0])
        assert matrix[0, position] == pytest.approx(expected, rel=1e-4)
