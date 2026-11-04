"""structure_dockq: DockQ against the official DockQ implementation."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.reader import read_source
from src.task.step.steps.structure_dockq import interface_score

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"


def test_interface_score_formula():
    assert interface_score(1.0, 0.0, 0.0) == pytest.approx(1.0)
    assert interface_score(0.0, 1.5, 8.5) == pytest.approx((0.0 + 0.5 + 0.5) / 3.0)


def _form():
    return read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def _run(form, native, tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_dockq", "inputs": ["pdb"], "params": {"output": "dockq", "native_path": str(native), "receptor_chains": "L,M", "ligand_chains": "A,B"}}])
    return ctx["dockq"]


def test_identical_complex_scores_one(tmp_path):
    form = _form()
    result = _run(form, FIXTURE, tmp_path)
    assert result.dims == ["complex", "statistic"]
    assert float(result.data[0, 0]) == pytest.approx(1.0)
    assert float(result.data[0, 3]) == pytest.approx(1.0, abs=1e-3)


def test_against_official_dockq_on_perturbed_model(tmp_path):
    import sys

    binary = shutil.which("DockQ")
    if not binary:
        candidate = Path(sys.executable).parent / "DockQ"
        binary = str(candidate) if candidate.is_file() else ""
    if not binary:
        pytest.skip("DockQ CLI is not installed")
    lines = FIXTURE.read_text().splitlines()
    shifted = []
    for line in lines:
        if line.startswith("ATOM") and line[21] in ("A", "B"):
            x = float(line[30:38]) + 2.0
            z = float(line[46:54]) + 1.0
            line = line[:30] + f"{x:8.3f}" + line[38:46] + f"{z:8.3f}" + line[54:]
        shifted.append(line)
    model = tmp_path / "model.pdb"
    model.write_text("\n".join(shifted) + "\n")
    official = subprocess.run([binary, str(model), str(FIXTURE), "--json", str(tmp_path / "d.json")], capture_output=True, text=True)
    assert official.returncode == 0, official.stderr
    data = json.loads((tmp_path / "d.json").read_text())
    pair = data["best_result"]["AL"]
    oracle = float(pair["DockQ"])
    form = read_source(str(model), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task2"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_dockq", "inputs": ["pdb"], "params": {"output": "dockq", "native_path": str(FIXTURE), "receptor_chains": "A", "ligand_chains": "L"}}])
    result = ctx["dockq"]
    ours = float(result.data[0, 3])
    assert abs(ours - oracle) < 0.08, (ours, oracle)


def test_errors(tmp_path):
    form = _form()
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "structure_dockq", "inputs": ["pdb"], "params": {"output": "dockq", "native_path": str(tmp_path / "none.pdb"), "receptor_chains": "L", "ligand_chains": "A"}}])
    with pytest.raises(StepError, match="are required"):
        run(ctx, [{"name": "structure_dockq", "inputs": ["pdb"], "params": {"output": "dockq", "native_path": str(FIXTURE)}}])
