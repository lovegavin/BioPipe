"""Tests for the ProteinMPNN noise-robustness operator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_noise_robustness import (
    noise_row,
    parse_levels,
    pdb_coordinates,
    perturb_coordinates,
    write_perturbed,
)

PDB_TEXT = (
    "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N\n"
    "ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00 20.00           C\n"
    "ATOM      3  C   ALA A   1       2.000   0.000   0.000  1.00 20.00           C\n"
    "END\n"
)

FAKE_RUNNER = '''\
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--pdb_path", required=True)
parser.add_argument("--out_folder", required=True)
parser.add_argument("--num_seq_per_target", type=int, default=8)
parser.add_argument("--sampling_temp", default="0.1")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--suppress_print", default="1")
parser.add_argument("--model_name", default="v_48_020")
parser.add_argument("--path_to_model_weights", default="")
parser.add_argument("--pdb_path_chains", default="")
args, _unknown = parser.parse_known_args()

structure = Path(args.pdb_path)
out = Path(args.out_folder) / "seqs" / (structure.stem + ".fa")
out.parent.mkdir(parents=True, exist_ok=True)
records = []
for index in range(2):
    records.append(
        ">T={}, sample={}, score={}, global_score={}, seq_recovery={}\\nAAAA\\n".format(
            structure.stem, index + 1, 1.0 + index, 2.0 + index, 0.4 + 0.1 * index
        )
    )
out.write_text("".join(records), encoding="utf-8")

capture = os.environ.get("OPERON_TEST_CAPTURE")
if capture:
    Path(capture).write_text(
        json.dumps(
            {
                "pdb_path": args.pdb_path,
                "weights": args.path_to_model_weights,
                "cuda": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "seed": args.seed,
                "model_name": args.model_name,
            }
        ),
        encoding="utf-8",
    )
'''


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "proteinmpnn"
    weights = repo / "vanilla_model_weights"
    weights.mkdir(parents=True)
    (weights / "v_48_020.pt").write_bytes(b"stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    return repo


def _structure(tmp_path: Path) -> Path:
    path = tmp_path / "mini.pdb"
    path.write_text(PDB_TEXT, encoding="utf-8")
    return path


def _run(tmp_path: Path, repo: Path, structure: Path, **params) -> Context:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_noise_robustness",
                "inputs": [],
                "params": {
                    "structure_path": str(structure),
                    "proteinmpnn_path": str(repo),
                    "output": "noise",
                    **params,
                },
            }
        ],
    )
    return ctx


def test_parse_levels() -> None:
    assert parse_levels("2, 0 1") == [0.0, 1.0, 2.0]
    assert parse_levels("0.5") == [0.5]
    with pytest.raises(StepError, match="at least one non-negative"):
        parse_levels("  ")
    with pytest.raises(StepError, match="is not a number"):
        parse_levels("0,abc")
    with pytest.raises(StepError, match="must be >= 0"):
        parse_levels("-0.5")
    with pytest.raises(StepError, match="is repeated"):
        parse_levels("1,1")
    with pytest.raises(StepError, match="at most 5"):
        parse_levels("0,1,2,3,4,5")


def test_coordinate_round_trip() -> None:
    coordinates, lines = pdb_coordinates(PDB_TEXT)
    assert coordinates.shape == (3, 3)
    assert lines == [0, 1, 2]
    assert np.array_equal(
        coordinates, np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    )
    unchanged = perturb_coordinates(coordinates, 0.0, np.random.default_rng(3))
    assert np.array_equal(unchanged, coordinates)
    assert write_perturbed(PDB_TEXT, lines, unchanged) == PDB_TEXT

    shifted = perturb_coordinates(coordinates, 0.5, np.random.default_rng(3))
    assert not np.allclose(shifted, coordinates)
    rewritten = write_perturbed(PDB_TEXT, lines, shifted)
    reread, _ = pdb_coordinates(rewritten)
    assert reread == pytest.approx(shifted, abs=1e-3)
    # The record layout (name, residue, occupancy, element) must survive.
    assert rewritten.splitlines()[0][:30] == PDB_TEXT.splitlines()[0][:30]
    assert rewritten.splitlines()[0][54:] == PDB_TEXT.splitlines()[0][54:]


def test_perturbation_is_seeded() -> None:
    coordinates, _ = pdb_coordinates(PDB_TEXT)
    first = perturb_coordinates(coordinates, 1.0, np.random.default_rng(11))
    second = perturb_coordinates(coordinates, 1.0, np.random.default_rng(11))
    third = perturb_coordinates(coordinates, 1.0, np.random.default_rng(12))
    assert np.array_equal(first, second)
    assert not np.array_equal(first, third)


def test_noise_row_summarises_records() -> None:
    records = [
        {"score": 1.0, "global_score": 2.0, "seq_recovery": 0.4},
        {"score": 2.0, "global_score": 3.0, "seq_recovery": 0.6},
    ]
    row = noise_row(records, 1.5, 2)
    assert row == pytest.approx((1.5, 2.0, 2.0, 1.5, 2.5, 0.5, 0.4))


def test_runner_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    capture = tmp_path / "captured.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    ctx = _run(
        tmp_path,
        repo,
        structure,
        noise_levels="0,1",
        replicates=1,
        num_seq_per_target=2,
        device="cpu",
    )
    form = ctx["noise"]
    assert form.dims == ["noise", "statistic"]
    assert form.data.shape == (2, 7)
    assert form.data[:, 0].tolist() == [0.0, 1.0]
    assert form.data[0, 2] == pytest.approx(2.0)  # n_designs
    assert form.data[0, 3] == pytest.approx(1.5)  # mean_score
    assert form.data[0, 4] == pytest.approx(2.5)  # mean_global_score
    assert form.data[0, 5] == pytest.approx(0.45)  # mean_seq_recovery
    assert form.data[0, 6] == pytest.approx(0.4)  # min_seq_recovery
    assert set(form.labels["noise"]) == {"sigma0:r0", "sigma1:r0"}
    assert form.info["noise_levels"] == [0.0, 1.0]
    assert form.info["n_rows"] == 2

    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload["pdb_path"].endswith(".pdb")
    assert "noise_" in Path(payload["pdb_path"]).name
    assert payload["weights"].replace("\\", "/").endswith("vanilla_model_weights")
    assert payload["cuda"] == ""
    assert payload["seed"] == 0
    assert payload["model_name"] == "v_48_020"

    exports = sorted((tmp_path / "task").rglob("*proteinmpnn_noise_robustness*.json"))
    assert exports
    exported = json.loads(exports[-1].read_text(encoding="utf-8"))
    assert exported["n_rows"] == 2


def test_validation_errors(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="structure_path .* is not a file"):
        _run(tmp_path, repo, tmp_path / "missing.pdb")
    text_file = tmp_path / "structure.txt"
    text_file.write_text(PDB_TEXT, encoding="utf-8")
    with pytest.raises(StepError, match="must be a .pdb file"):
        _run(tmp_path, repo, text_file)
    with pytest.raises(StepError, match="is not a directory"):
        _run(tmp_path, tmp_path / "absent-repo", structure)
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(StepError, match="does not exist; point proteinmpnn_path"):
        _run(tmp_path, bare, structure)
    with pytest.raises(StepError, match="weights directory"):
        _run(tmp_path, repo, structure, weights_path=str(tmp_path / "absent-weights"))
    with pytest.raises((StepError, ValueError), match="model_name"):
        _run(tmp_path, repo, structure, model_name="v_99_999")
    with pytest.raises((StepError, ValueError), match="replicates"):
        _run(tmp_path, repo, structure, replicates=9)
    with pytest.raises(StepError, match="noise level 'abc' is not a number"):
        _run(tmp_path, repo, structure, noise_levels="0,abc")
