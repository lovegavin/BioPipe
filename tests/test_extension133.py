"""Tests for the LigandMPNN score operator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.ligandmpnn_score import (
    LigandMpnnScoreStep,
    label_order,
    score_statistics,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"

FAKE_SCORER = r'''import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

args = sys.argv[1:]


def value(flag):
    return args[args.index(flag) + 1] if flag in args else None


Path("captured.json").write_text(
    json.dumps({"argv": args, "cwd": str(Path.cwd()), "cuda": os.environ.get("CUDA_VISIBLE_DEVICES")})
)
pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
out.mkdir(parents=True, exist_ok=True)
log_probs = np.full((2, 3, 21), -3.0)
log_probs[0, 0, 0] = -0.5
log_probs[0, 1, 1] = -1.0
log_probs[0, 2, 2] = -3.0
log_probs[1, 0, 0] = -1.5
log_probs[1, 1, 1] = -2.0
log_probs[1, 2, 2] = -3.0
payload = {
    "log_probs": torch.tensor(log_probs, dtype=torch.float32),
    "native_sequence": torch.tensor([0, 1, 2]),
    "mask": torch.tensor([1.0, 1.0, 1.0]),
    "residue_names": {0: "A1", 1: "A10", 2: "A2"},
    "sequence": ["A", "C", "D"],
    "seed": 1,
    "alphabet": "ACDEFGHIKLMNPQRSTVWYX",
}
torch.save(payload, out / (pdb.stem + ".pt"))
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path, scorer_name="score.py", weights_name="ligandmpnn_v_32_010_25.pt", body=None):
    repo = tmp_path / "LigandMPNN"
    repo.mkdir(parents=True)
    (repo / scorer_name).write_text(body if body is not None else FAKE_SCORER)
    (repo / "model_params").mkdir()
    weights = repo / "model_params" / weights_name
    weights.write_text("stub weights")
    return repo, weights


def _run(params):
    params = {"python_executable": sys.executable, **params}
    ctx = Ctx(params)
    step = LigandMpnnScoreStep()
    step.run(ctx, [])
    return step, ctx["out"]


def _base(repo, weights):
    return {"structure_path": str(FIXTURE), "ligandmpnn_path": str(repo), "weights_path": str(weights)}


def test_score_statistics_matches_hand_calculation():
    log_probs = np.full((2, 3, 21), -3.0)
    log_probs[0, 0, 0] = -0.5
    log_probs[1, 0, 0] = -1.5
    log_probs[0, 1, 1] = -1.0
    log_probs[1, 1, 1] = -2.0
    payload = {
        "log_probs": log_probs,
        "native_sequence": np.array([0, 1, 2]),
        "mask": np.array([1.0, 1.0, 0.0]),
        "residue_names": {0: "A1", 1: "A2", 2: "A3"},
    }
    data, labels = score_statistics(payload)
    assert labels == ["A1", "A2"]
    np.testing.assert_allclose(data, [[-1.0, 0.5], [-1.5, 0.5]], rtol=1e-12)


def test_score_statistics_errors():
    with pytest.raises(StepError, match="has no 'log_probs' entry"):
        score_statistics({"native_sequence": [0], "mask": [1], "residue_names": {}})
    with pytest.raises(StepError, match="no scored residues"):
        score_statistics(
            {
                "log_probs": np.zeros((1, 2, 21)),
                "native_sequence": np.array([0, 1]),
                "mask": np.array([0.0, 0.0]),
                "residue_names": {0: "A1", 1: "A2"},
            }
        )
    with pytest.raises(StepError, match="unexpected shape"):
        score_statistics(
            {
                "log_probs": np.zeros((2, 2, 21)),
                "native_sequence": np.array([0]),
                "mask": np.array([1.0, 1.0]),
                "residue_names": {0: "A1", 1: "A2"},
            }
        )


def test_label_order_sorts_numerically():
    labels = ["A10", "A2", "A1", "B1", "A2A"]
    assert sorted(labels, key=label_order) == ["A1", "A2", "A2A", "A10", "B1"]


def test_score_outputs_and_payload_parse(tmp_path):
    repo, weights = _repo(tmp_path)
    _, out = _run({**_base(repo, weights), "number_of_batches": 2, "batch_size": 1})
    assert list(out.dims) == ["residue", "statistic"]
    assert list(out.labels["residue"].keys()) == ["A1", "A2", "A10"]
    assert list(out.labels["statistic"].keys()) == ["mean_log_prob", "std_log_prob"]
    np.testing.assert_allclose(
        np.asarray(out.data),
        np.array([[-1.0, 0.5], [-3.0, 0.0], [-1.5, 0.5]], dtype=np.float32),
        rtol=1e-6,
    )
    assert out.info["sequence"] == "ACD"
    assert out.info["n_residues"] == 3
    assert out.info["total_log_prob"] == pytest.approx(-5.5, rel=1e-6)
    assert out.info["mean_log_prob"] == pytest.approx(-11.0 / 6.0, rel=1e-6)


def test_score_command_and_environment(tmp_path):
    repo, weights = _repo(tmp_path, weights_name="proteinmpnn_v_48_020.pt")
    _run(
        {
            **_base(repo, weights),
            "model_type": "protein_mpnn",
            "chains_to_design": "C",
            "seed": 9,
            "number_of_batches": 3,
            "batch_size": 2,
            "use_sequence": False,
            "ligand_mpnn_use_atom_context": False,
        }
    )
    captured = json.loads((repo / "captured.json").read_text())
    argv = captured["argv"]

    def flag(name):
        return argv[argv.index(name) + 1]

    assert captured["cwd"] == str(repo)
    assert captured["cuda"] == ""
    assert flag("--model_type") == "protein_mpnn"
    assert flag("--checkpoint_protein_mpnn") == weights.as_posix()
    assert flag("--pdb_path") == FIXTURE.as_posix()
    assert flag("--seed") == "9"
    assert flag("--number_of_batches") == "3"
    assert flag("--batch_size") == "2"
    assert flag("--use_sequence") == "0"
    assert flag("--autoregressive_score") == "1"
    assert flag("--single_aa_score") == "0"
    assert flag("--ligand_mpnn_use_atom_context") == "0"
    assert flag("--chains_to_design") == "C"


def test_score_export_and_print(tmp_path, capsys):
    repo, weights = _repo(tmp_path)
    step, _ = _run(_base(repo, weights))
    record = step.export(Ctx({}))
    assert record["structure_path"] == str(FIXTURE)
    assert "ligandmpnn_score: 3 residues" in capsys.readouterr().out


def test_score_errors(tmp_path):
    repo, weights = _repo(tmp_path)
    with pytest.raises(StepError, match="structure_path is required"):
        _run({**_base(repo, weights), "structure_path": ""})
    with pytest.raises(StepError, match="is not a file"):
        _run({**_base(repo, weights), "structure_path": str(tmp_path / "nope.pdb")})
    (tmp_path / "notrepo").mkdir()
    with pytest.raises(StepError, match="does not look like a LigandMPNN checkout"):
        _run({**_base(repo, weights), "ligandmpnn_path": str(tmp_path / "notrepo")})
    with pytest.raises(StepError, match="weights_path is required"):
        _run({**_base(repo, weights), "weights_path": ""})
    with pytest.raises(StepError, match="model_type must be one of"):
        _run({**_base(repo, weights), "model_type": "esm"})
    with pytest.raises(StepError, match="number_of_batches must be at least 1"):
        _run({**_base(repo, weights), "number_of_batches": 0})
    with pytest.raises(StepError, match="batch_size must be between 1 and 64"):
        _run({**_base(repo, weights), "batch_size": 0})


def test_score_failure_and_missing_payload(tmp_path):
    repo, weights = _repo(tmp_path / "failed", body="import sys\nprint('bad', file=sys.stderr)\nsys.exit(4)\n")
    with pytest.raises(StepError, match="exit code 4.*bad"):
        _run(_base(repo, weights))
    repo, weights = _repo(tmp_path / "empty")
    (repo / "score.py").write_text("import sys\nsys.exit(0)\n")
    with pytest.raises(StepError, match="produced no statistics file"):
        _run(_base(repo, weights))


REPO = os.environ.get("OPERON_LIGANDMPNN_PATH", "")
WEIGHTS = os.environ.get("OPERON_LIGANDMPNN_WEIGHTS", "")
REAL = bool(REPO and WEIGHTS and Path(REPO, "score.py").is_file() and Path(WEIGHTS).is_file())


@pytest.mark.skipif(not REAL, reason="set OPERON_LIGANDMPNN_PATH and OPERON_LIGANDMPNN_WEIGHTS for the official oracle")
def test_official_scorer_oracle(tmp_path):
    params = {
        "structure_path": str(FIXTURE),
        "ligandmpnn_path": REPO,
        "weights_path": WEIGHTS,
        "model_type": "ligand_mpnn",
        "seed": 1,
        "number_of_batches": 1,
        "batch_size": 1,
    }
    _, out = _run(params)
    assert out.data.shape == (16, 2)
    assert np.isfinite(np.asarray(out.data)).all()

    target = tmp_path / "manual"
    command = [
        sys.executable,
        str(Path(REPO) / "score.py"),
        "--pdb_path",
        FIXTURE.as_posix(),
        "--out_folder",
        target.as_posix(),
        "--model_type",
        "ligand_mpnn",
        "--checkpoint_ligand_mpnn",
        Path(WEIGHTS).as_posix(),
        "--seed",
        "1",
        "--number_of_batches",
        "1",
        "--batch_size",
        "1",
        "--use_sequence",
        "1",
        "--autoregressive_score",
        "1",
        "--single_aa_score",
        "0",
    ]
    subprocess.run(
        command,
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
    )
    import torch

    payload = torch.load(target / f"{FIXTURE.stem}.pt", map_location="cpu", weights_only=False)
    data, labels = score_statistics(payload)
    expected = dict(zip(labels, data[:, 0]))
    actual = dict(zip(out.labels["residue"].keys(), out.data[:, 0]))
    for label in expected:
        assert actual[label] == pytest.approx(float(expected[label]), rel=1e-5)
