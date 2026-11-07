"""Tests for the ProteinMPNN tied-position design operator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_tied_design import parse_tied_groups, tied_payload

PDB_TEXT = (
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    "ATOM      2  CA  ALA A   2       3.800   0.000   0.000  1.00 20.00           C\n"
    "ATOM      3  CA  ALA B   1       0.000  10.000   0.000  1.00 20.00           C\n"
    "ATOM      4  CA  ALA B   2       3.800  10.000   0.000  1.00 20.00           C\n"
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
parser.add_argument("--tied_positions_jsonl", default="")
args, _unknown = parser.parse_known_args()

structure = Path(args.pdb_path)
out = Path(args.out_folder) / "seqs" / (structure.stem + ".fa")
out.parent.mkdir(parents=True, exist_ok=True)
records = []
for index in range(2):
    records.append(
        ">T={}, sample={}, score={}, global_score={}, seq_recovery={}\\nACDEFG\\n".format(
            structure.stem, index + 1, 1.5 - 0.5 * index, 1.0, 0.5
        )
    )
out.write_text("".join(records), encoding="utf-8")

payload = {}
if args.tied_positions_jsonl:
    payload = json.loads(Path(args.tied_positions_jsonl).read_text(encoding="utf-8"))
capture = os.environ.get("OPERON_TEST_CAPTURE")
if capture:
    Path(capture).write_text(
        json.dumps(
            {
                "pdb_path": args.pdb_path,
                "weights": args.path_to_model_weights,
                "payload": payload,
                "cuda": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "args": args.__dict__,
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
    payload = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "tied_positions": "A:1,2|B:1,2",
        "output": "designs",
        **params,
    }
    run(ctx, [{"name": "proteinmpnn_tied_design", "inputs": [], "params": payload}])
    return ctx


def test_parse_tied_groups() -> None:
    assert parse_tied_groups("A:1,2|B:1,2") == {"A": [1, 2], "B": [1, 2]}
    assert parse_tied_groups("A:1,2;B:3,4") == {"A": [1, 2], "B": [3, 4]}
    assert parse_tied_groups("A: 1 2 | B: 5 6") == {"A": [1, 2], "B": [5, 6]}
    with pytest.raises(StepError, match="tied_positions is required"):
        parse_tied_groups("")
    with pytest.raises(StepError, match="at least two chains"):
        parse_tied_groups("A:1,2")
    with pytest.raises(StepError, match="is not of the form"):
        parse_tied_groups("AB|CD")
    with pytest.raises(StepError, match="appears twice"):
        parse_tied_groups("A:1|A:2")
    with pytest.raises(StepError, match="is not an integer"):
        parse_tied_groups("A:x|B:1")
    with pytest.raises(StepError, match="positive residue numbers"):
        parse_tied_groups("A:0|B:1")
    with pytest.raises(StepError, match="lists position 2 twice"):
        parse_tied_groups("A:2,2|B:1,3")
    with pytest.raises(StepError, match="same number of positions"):
        parse_tied_groups("A:1,2|B:1,2,3")


def test_tied_payload_maps_author_numbers() -> None:
    tied = parse_tied_groups("A:10,11|B:20,21")
    payload = tied_payload(tied, "", "mini", {"A": [10, 11, 12], "B": [20, 21, 22]})
    assert payload == {
        "mini": [
            {"A": [10], "B": [20]},
            {"A": [11], "B": [21]},
        ]
    }
    with pytest.raises(StepError, match="not in the structure file"):
        tied_payload(tied, "", "mini", {"A": [10, 11]})
    with pytest.raises(StepError, match="not author residue numbers"):
        tied_payload(tied, "", "mini", {"A": [10, 11], "B": [20, 99]})
    with pytest.raises(StepError, match="not among the designed chains"):
        tied_payload(tied, "A", "mini", {"A": [10, 11], "B": [20, 21]})


def test_runner_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    capture = tmp_path / "captured.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    ctx = _run(tmp_path, repo, structure, num_seq_per_target=2, device="cpu")

    form = ctx["designs"]
    assert form.dims == ["design", "statistic"]
    assert form.data.shape == (2, 2)
    assert form.data[:, 0].tolist() == pytest.approx([1.5, 1.0])
    assert form.data[:, 1].tolist() == pytest.approx([1.0, 1.0])
    assert form.labels["design"] == {"design1": 0, "design2": 1}
    assert form.labels["statistic"] == {"score": 0, "global_score": 1}
    assert form.info["n_tied_sites"] == 2
    assert form.info["n_tied_residues"] == 4
    assert form.info["tied_positions"] == {"A": [1, 2], "B": [1, 2]}
    assert form.info["sequences"] == ["ACDEFG", "ACDEFG"]

    captured = json.loads(capture.read_text(encoding="utf-8"))
    assert captured["payload"] == {
        "mini": [{"A": [1], "B": [1]}, {"A": [2], "B": [2]}]
    }
    assert captured["cuda"] == ""
    assert captured["args"]["tied_positions_jsonl"]
    assert captured["weights"].replace("\\", "/").endswith("proteinmpnn/vanilla_model_weights")


def test_router_validation_errors(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="structure_path is required"):
        _run(tmp_path, repo, structure, structure_path="")
    with pytest.raises(StepError, match="is not a file|must be a .pdb file"):
        _run(tmp_path, repo, structure, structure_path=str(tmp_path / "x.txt"))
    with pytest.raises(StepError, match="does not exist"):
        _run(tmp_path, repo, structure, proteinmpnn_path=str(tmp_path / "missing"))
    with pytest.raises((StepError, ValueError), match="model_name|v_99"):
        _run(tmp_path, repo, structure, model_name="v_99")
    with pytest.raises((StepError, ValueError), match="device|tpu"):
        _run(tmp_path, repo, structure, device="tpu")


def test_tied_payload_in_runner_rejects_unknown_chain(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="chain C is not in the structure file"):
        _run(tmp_path, repo, structure, tied_positions="A:1|C:1")
