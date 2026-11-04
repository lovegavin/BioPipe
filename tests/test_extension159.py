"""Tests for the v1.30.0 proteinmpnn_ensemble_score operator."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_ensemble_score import (
    ProteinmpnnEnsembleScoreStep,
    parse_models,
)

FAKE_RUNNER = r'''
import json
import os
import sys
from pathlib import Path

import numpy as np

args = sys.argv[1:]
model = args[args.index("--model_name") + 1]
out_folder = Path(args[args.index("--out_folder") + 1])
pdb = Path(args[args.index("--pdb_path") + 1])
weights = {"v_48_002": 0.0, "v_48_010": 1.0, "v_48_020": 2.0, "v_48_030": 3.0}
folder = out_folder / "score_only"
folder.mkdir(parents=True, exist_ok=True)
for index in (1, 2):
    np.savez(
        folder / (pdb.stem + "_fasta_" + str(index) + ".npz"),
        score=np.asarray([[10.0 * index + weights[model]]]),
        global_score=np.asarray([[100.0]]),
        S=np.zeros((1, 5), dtype=np.int64),
        seq_str=np.asarray("ACDEF"),
    )
Path(os.environ["FAKE_MPNN_LOG"]).write_text(
    json.dumps({"argv": args, "cwd": os.getcwd(), "cuda": os.environ.get("CUDA_VISIBLE_DEVICES")}),
    encoding="utf-8",
)
'''


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    for model in ("v_48_002", "v_48_010", "v_48_020", "v_48_030"):
        (repo / "vanilla_model_weights" / f"{model}.pt").write_bytes(b"w")
    return repo


def _structure(tmp_path: Path) -> Path:
    path = tmp_path / "mini.pdb"
    path.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
        "ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00  0.00           C\n"
        "END\n",
        encoding="utf-8",
    )
    return path


def _fasta(tmp_path: Path) -> Path:
    path = tmp_path / "seqs.fasta"
    path.write_text(">one\nACDEF\n>two\nGHIKL\n", encoding="utf-8")
    return path


def _run(step, params, forms=()):
    class Ctx(dict):
        def __init__(self, params):
            self.step_params = {"output": "out", **params}
            self.metadata = {}

    ctx = Ctx(params)
    step.run(ctx, list(forms))
    return ctx[params.get("output", "out")]


def test_parse_models() -> None:
    assert parse_models("v_48_002, v_48_020") == ["v_48_002", "v_48_020"]
    assert parse_models("v_48_002 v_48_010") == ["v_48_002", "v_48_010"]
    with pytest.raises(StepError, match="unknown"):
        parse_models("v_99_999")
    with pytest.raises(StepError, match="listed twice"):
        parse_models("v_48_002,v_48_002")
    with pytest.raises(StepError, match="at least one model"):
        parse_models("")


def test_ensemble_matrix(tmp_path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    log = tmp_path / "captured.json"
    monkeypatch.setenv("FAKE_MPNN_LOG", str(log))
    step = ProteinmpnnEnsembleScoreStep()
    params = {
        "structure_path": str(_structure(tmp_path)),
        "fasta_path": str(_fasta(tmp_path)),
        "proteinmpnn_path": str(repo),
        "python_executable": sys.executable,
        "models": "v_48_002,v_48_020",
        "device": "cpu",
    }
    form = _run(step, params)
    assert list(form.dims) == ["sequence", "model"]
    assert list(form.labels["sequence"]) == ["one", "two"]
    assert list(form.labels["model"]) == ["v_48_002", "v_48_020"]
    matrix = np.asarray(form.data)
    assert matrix.shape == (2, 2)
    np.testing.assert_allclose(matrix[:, 0], [10.0, 20.0], rtol=1e-6)
    np.testing.assert_allclose(matrix[:, 1], [12.0, 22.0], rtol=1e-6)
    assert form.info["models"] == ["v_48_002", "v_48_020"]
    assert form.info["model_mean_nll"]["v_48_002"] == pytest.approx(15.0)
    assert form.info["sequences"] == ["ACDEF", "GHIKL"]
    captured = json.loads(log.read_text(encoding="utf-8"))
    assert captured["cwd"] == str(repo)
    assert captured["cuda"] == ""
    export = step.export(None)
    assert export["n_sequences"] == 2


def test_ensemble_errors(tmp_path) -> None:
    repo = _repo(tmp_path)
    base = {
        "structure_path": str(_structure(tmp_path)),
        "fasta_path": str(_fasta(tmp_path)),
        "proteinmpnn_path": str(repo),
        "python_executable": sys.executable,
        "models": "v_48_002",
    }
    step = ProteinmpnnEnsembleScoreStep()
    with pytest.raises(StepError, match="structure_path"):
        _run(step, {**base, "structure_path": str(tmp_path / "nope.pdb")})
    with pytest.raises(StepError, match="fasta_path"):
        _run(step, {**base, "fasta_path": str(tmp_path / "nope.fasta")})
    with pytest.raises(StepError, match="not a directory"):
        _run(step, {**base, "proteinmpnn_path": str(tmp_path / "nope")})
    with pytest.raises(StepError, match="weights"):
        _run(step, {**base, "weights_path": str(tmp_path / "no_weights")})
    with pytest.raises(StepError, match="device"):
        _run(step, {**base, "device": "tpu"})
