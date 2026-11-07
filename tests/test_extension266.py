from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context import Context
from src.task.runner import run


def _ctx(task_dir: Path, out_name: str, params: dict) -> Context:
    ctx = Context(str(task_dir / "task"), {"params": {}})
    ctx.step_params = {"output": out_name, **params}
    return ctx

import json

from src.task.step.steps.proteinmpnn_omit_design import parse_omit

FAKE_RUNNER = """import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
options = {}
index = 0
while index < len(args):
    if args[index].startswith("--"):
        options[args[index]] = args[index + 1] if index + 1 < len(args) else True
        index += 2
    else:
        index += 1
capture = os.environ.get("OPERON_TEST_CAPTURE")
if capture:
    Path(capture).write_text(json.dumps({"options": options, "argv": args}))
out = Path(options["--out_folder"]) / "seqs"
out.mkdir(parents=True, exist_ok=True)
pdb = Path(options["--pdb_path"])
lines = [
    f">{pdb.stem}, sample=1, score=0.5, global_score=0.4, seq_recovery=0.9",
    "AAAGGG",
    f">{pdb.stem}, sample=2, score=0.7, global_score=0.6, seq_recovery=0.8",
    "AAAVVV",
]
(out / (pdb.stem + ".fa")).write_text("\\n".join(lines) + "\\n")
"""


def _params(tmp_path: Path) -> dict:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"0")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    structure = tmp_path / "mini.pdb"
    structure.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 10.00           N\n"
        "ATOM      2  CA  ALA A   1       1.400   0.000   0.000  1.00 10.00           C\n"
        "ATOM      3  C   ALA A   1       2.100   1.200   0.000  1.00 10.00           C\n"
        "END\n",
        encoding="utf-8",
    )
    return {
        "structure_path": str(structure),
        "omit_AAs": "C",
        "num_seq_per_target": 2,
        "proteinmpnn_path": str(repo),
    }


def test_parse_omit():
    assert parse_omit("C") == "C"
    assert parse_omit("c, M") == "CM"
    assert parse_omit("C; C M") == "CM"
    with pytest.raises(StepError, match="not a standard amino-acid letter"):
        parse_omit("CJ")
    with pytest.raises(StepError, match="omit_AAs must list at least one"):
        parse_omit("")
    with pytest.raises(StepError, match="at least one amino acid must remain"):
        parse_omit("ACDEFGHIKLMNPQRSTVWY")


def test_run_designs_without_omitted_residues(tmp_path, monkeypatch):
    params = _params(tmp_path)
    capture = tmp_path / "capture.json"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))
    ctx = _ctx(tmp_path, "designs", params)
    run(ctx, [{"name": "proteinmpnn_omit_design", "inputs": [], "params": params}])
    form = ctx["designs"]
    assert form.dims == ["design", "statistic"]
    assert form.data.shape == (2, 2)
    assert list(form.labels["design"]) == ["design1", "design2"]
    assert form.info["omit_AAs"] == "C"
    payload = json.loads(capture.read_text())
    assert payload["options"]["--omit_AAs"] == "C"
    assert payload["options"]["--num_seq_per_target"] == "2"
    assert form.info["sequences"] == ["AAAGGG", "AAAVVV"]


def test_leaked_residues_are_rejected(tmp_path, monkeypatch):
    params = _params(tmp_path)
    params["omit_AAs"] = "A"
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(tmp_path / "capture.json"))
    ctx = _ctx(tmp_path, "designs", params)
    with pytest.raises(StepError, match="omitted residues"):
        run(ctx, [{"name": "proteinmpnn_omit_design", "inputs": [], "params": params}])


def test_validation_errors(tmp_path):
    params = _params(tmp_path)
    cases = [
        ("structure_path", str(tmp_path / "missing.pdb"), "is not a file"),
        ("proteinmpnn_path", str(tmp_path / "nope"), "protein_mpnn_run.py was not found"),
        ("chains", "Z", "chains Z are not in the structure file"),
    ]
    for key, value, message in cases:
        bad = dict(params)
        bad[key] = value
        ctx = _ctx(tmp_path, "designs", bad)
        with pytest.raises(StepError, match=message):
            run(ctx, [{"name": "proteinmpnn_omit_design", "inputs": [], "params": bad}])
    bad = dict(params)
    bad["structure_path"] = str(Path(params["structure_path"]).with_suffix(".txt"))
    Path(bad["structure_path"]).write_text("x")
    ctx = _ctx(tmp_path, "designs", bad)
    with pytest.raises(StepError, match="must name a .pdb file"):
        run(ctx, [{"name": "proteinmpnn_omit_design", "inputs": [], "params": bad}])


def test_schema_errors_are_surfaced(tmp_path):
    params = _params(tmp_path)
    bad = dict(params)
    bad["device"] = "tpu"
    ctx = _ctx(tmp_path, "designs", bad)
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "proteinmpnn_omit_design", "inputs": [], "params": bad}])
