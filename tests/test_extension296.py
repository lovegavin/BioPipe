"""Contract tests for interface_mmgbsa_delta."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


import pytest

pytest.importorskip("openmm")
pytest.importorskip("pdbfixer")

from src.core.errors import StepError
from src.task.step.steps import interface_mmgbsa_delta as module


def test_parse_chains():
    assert module.parse_chains("a, b", "binder") == ("A", "B")
    with pytest.raises(StepError, match="must name at least one chain"):
        module.parse_chains("", "binder")


def test_classify_force():
    assert module.classify_force("HarmonicBondForce") == "bonded"
    assert module.classify_force("NonbondedForce") == "nonbonded"
    assert module.classify_force("CustomGBForce") == "gb"
    assert module.classify_force("CMMotionRemover") == "other"


def test_validation(tmp_path):
    from src.core.forms import Form
    import numpy as np

    form = Form(data=np.zeros((1, 2)), dims=["atom", "field"], labels={"atom": {"a": 0}, "field": {"x": 0, "y": 1}}, info={})
    step = module.InterfaceMmgbsaDeltaStep()
    with pytest.raises(StepError, match="binder_chains must name at least one chain"):
        step.run(_ctx({"output": "e"}), [form])
    with pytest.raises(StepError, match="are in both sides"):
        step.run(_ctx({"output": "e", "binder_chains": "A", "target_chains": "A"}), [form])


def _ctx(params):
    import tempfile

    from src.task.context import Context

    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx.step_params = params
    return ctx


def test_real_mmgbsa(tmp_path):
    import tempfile

    from src.reader import read_source
    from src.task.context import Context
    from src.task.runner import run

    lines = [
        line
        for line in open(str(ROOT / "tests" / "fixtures" / "vhh_1mel.pdb"))
        if line.startswith("ATOM") and line[21] in "ABLM"
    ]
    path = tmp_path / "complex.pdb"
    path.write_text("\n".join(lines) + "\nTER\nEND\n")
    form = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    run(
        ctx,
        [
            {
                "name": "interface_mmgbsa_delta",
                "inputs": ["pdb"],
                "params": {"output": "energy", "binder_chains": "A,B", "target_chains": "L,M"},
            }
        ],
    )
    result = ctx["energy"]
    assert result.data.shape == (5, 4)
    total = float(result.data[4, 3])
    assert abs(total - result.info["delta_total_kj"]) < 1e-2 * max(abs(total), 1)
    terms = result.data[:4, 3].astype(float)
    assert abs(terms.sum() - total) < 1e-2 * max(abs(total), 1)
