"""Tests for the hotspot-masked ProteinMPNN operator."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_hotspot_masked_design import (
    hotspot_mask,
    hotspot_table,
)
from src.task.step.steps.proteinmpnn_masked_design import pdb_chains

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"

FAKE_RUNNER = """import json
import sys
from pathlib import Path

out = Path(sys.argv[sys.argv.index("--out_folder") + 1])
pdb = Path(sys.argv[sys.argv.index("--pdb_path") + 1])
out.mkdir(parents=True, exist_ok=True)
(out / "seqs").mkdir(parents=True, exist_ok=True)
payload = ""
if "--fixed_positions_jsonl" in sys.argv:
    payload = Path(sys.argv[sys.argv.index("--fixed_positions_jsonl") + 1]).read_text()
capture = {"argv": sys.argv[1:], "cwd": str(Path.cwd()), "payload": payload}
Path(__import__("os").environ["OPERON_TEST_CAPTURE"]).write_text(json.dumps(capture))
header = (
    ">T="
    + pdb.stem
    + ", sample=1, score=1.25, global_score=1.5, seq_recovery=0.7"
)
(out / "seqs" / (pdb.stem + ".fa")).write_text(header + "\\nAAAA\\n")
"""


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "proteinmpnn"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"stub")
    return repo, weights


def _params(tmp_path: Path, repo: Path) -> dict:
    structure = tmp_path / "mini.pdb"
    if not structure.is_file():
        shutil.copyfile(FIXTURE, structure)
    return {
        "structure_path": str(structure),
        "binder_chains": "A",
        "target_chains": "L",
        "cutoff": 5.0,
        "top_n": 2,
        "proteinmpnn_path": str(repo),
        "output": "designs",
    }


def test_hotspot_table_ranks_by_contacts() -> None:
    labels = np.array(["A:ALA:1", "A:ALA:1", "A:GLY:2"], dtype=object)
    chains = np.array(["A", "A", "A"], dtype=object)
    numbers = np.array([1, 1, 2], dtype=np.int64)
    counts = np.array([3, 2, 5], dtype=np.int64)
    distances = np.array([4.0, 5.0, 3.0], dtype=np.float64)
    rows = hotspot_table(labels, chains, numbers, ["A"], counts, distances)
    assert [row["label"] for row in rows] == ["A:ALA:1", "A:GLY:2"]
    assert rows[0]["n_contacts"] == 5
    assert rows[0]["rank"] == 1
    assert rows[1]["n_contacts"] == 5
    assert rows[1]["rank"] == 2
    filtered = hotspot_table(labels, chains, numbers, ["A"], counts, distances, min_contacts=6)
    assert filtered == []
    other = hotspot_table(labels, chains, numbers, ["B"], counts, distances)
    assert other == []


def test_hotspot_mask_keeps_top_n() -> None:
    rows = [
        {"chain": "A", "number": 1, "n_contacts": 5},
        {"chain": "A", "number": 2, "n_contacts": 4},
        {"chain": "A", "number": 2, "n_contacts": 3},
    ]
    assert hotspot_mask(rows, 2) == {"A": [1, 2]}
    assert hotspot_mask(rows, 0) == {"A": [1, 2]}


def test_run_generates_designs_with_fixed_payload(tmp_path, monkeypatch) -> None:
    capture = tmp_path / "captured.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    repo, _weights = _repo(tmp_path)
    form = read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    params = _params(tmp_path, repo)
    ctx.step_params = params
    run(ctx, [{"name": "proteinmpnn_hotspot_masked_design", "inputs": ["pdb"], "params": params}])
    out = ctx["designs"]
    assert out.data.shape == (1, 2)
    assert out.info["n_hotspots"] == 2
    assert out.info["binder_chains"] == ["A"]
    captured = json.loads(capture.read_text())
    payload = json.loads(captured["payload"])
    fixed = payload["mini"]["A"]
    mask = out.info["mask"].get("A", [])
    total = len(pdb_chains(tmp_path / "mini.pdb")["A"])
    assert len(fixed) == total - len(mask)
    assert len(fixed) > 0
    assert out.info["hotspots"]
    assert all(label.startswith("A:") for label in out.info["hotspots"])


def test_top_n_above_interface_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(tmp_path / "captured.json"))
    repo, _weights = _repo(tmp_path)
    form = read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    params = _params(tmp_path, repo)
    params["top_n"] = 500
    with pytest.raises(StepError, match="top_n 500 exceeds the"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_hotspot_masked_design",
                    "inputs": ["pdb"],
                    "params": params,
                }
            ],
        )


def test_missing_structure_is_rejected(tmp_path) -> None:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    columns = ("x", "y", "z", "occupancy", "bfactor", "residue_number", "chain", "resname")
    ctx["pdb"] = Form(
        data=np.zeros((1, len(columns)), dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {"atom:1": 0},
            "field": {name: index for index, name in enumerate(columns)},
        },
    )
    with pytest.raises(StepError, match="structure_path is required"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_hotspot_masked_design",
                    "inputs": ["pdb"],
                    "params": {"structure_path": ""},
                }
            ],
        )
