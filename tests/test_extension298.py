"""Contract tests for structure_protonation_pka."""

from __future__ import annotations

import math

import pytest

from src.core.errors import StepError
from src.task.step.steps import structure_protonation_pka as module


PROPKA_TEXT = """
ASP  52 A   3.55     0 %    0.23  203
GLU  35 A   6.20    48 %    1.87  417
HIS  15 A   6.50    41 %    1.94  397
LYS  96 A  10.40     0 %    0.09  122
"""


def test_parse_propka_table():
    records = module.parse_propka(PROPKA_TEXT)
    assert [record["residue"] for record in records] == ["ASP", "GLU", "HIS", "LYS"]
    assert records[0]["pka"] == pytest.approx(3.55)
    assert records[2]["number"] == 15


def test_charge_at_ph_hand_case():
    assert module.charge_at_ph("ASP", 3.55, 7.0) == pytest.approx(-1 / (1 + 10 ** (3.55 - 7.0)), rel=1e-4)
    assert module.charge_at_ph("LYS", 10.4, 7.0) == pytest.approx(1 / (1 + 10 ** -3.4), rel=1e-4)
    assert module.charge_at_ph("HIS", 6.5, 7.0) == pytest.approx(1 / (1 + 10 ** 0.5), rel=1e-4)
    assert module.charge_at_ph("SER", 6.5, 7.0) == 0.0


def test_parse_pqr_charges():
    text = """ATOM      1  N   ASP A  52       0.000   0.000   0.000 -0.4000 1.8240
ATOM      2  CA  ASP A  52       1.000   0.000   0.000  0.1000 1.9080
ATOM      3  N   LYS A  96       2.000   0.000   0.000  0.3000 1.8240
"""
    charges = module.parse_pqr_charges(text)
    assert charges[("ASP", 52, "A")] == pytest.approx(-0.3)
    assert charges[("LYS", 96, "A")] == pytest.approx(0.3)


def test_validation(tmp_path):
    import numpy as np

    from src.core.forms import Form

    form = Form(data=np.zeros((1, 2)), dims=["atom", "field"], labels={"atom": {"a": 0}, "field": {"x": 0, "y": 1}}, info={})
    step = module.StructureProtonationPkaStep()
    with pytest.raises(StepError, match="ph must be between 0 and 14"):
        step.run(_ctx({"output": "pka", "ph": 20.0}), [form])


def _ctx(params):
    import tempfile

    from src.task.context import Context

    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx.step_params = params
    return ctx


def test_real_pdb2pqr(tmp_path):
    from pathlib import Path
    pytest.importorskip("pdb2pqr")
    from src.reader import read_source
    from src.task.context import Context
    from src.task.runner import run

    fixture = Path(__file__).parent / "fixtures/vhh_1mel.pdb"
    lines = [line.rstrip() for line in fixture.read_text().splitlines() if line.startswith("ATOM") and line[21] == "A"]
    path = tmp_path / "chain_a.pdb"
    path.write_text("\n".join(lines) + "\nTER\nEND\n")
    form = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(tmp_path / "task", {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_protonation_pka", "inputs": ["pdb"], "params": {"output": "pka", "ph": 7.0}}])
    result = ctx["pka"]
    assert result.data.shape[0] >= 5
    assert result.info["n_missing_pqr"] == 0
    assert abs(result.info["net_charge_hh"] - result.info["net_charge_pqr"]) < 1.0
    assert any(label.startswith("A:") for label in result.labels["residue"])


@pytest.mark.parametrize("binary, module_launch", [("pdb2pqr30", True), ("pdb2pqr", True), ("custom-pdb2pqr", False)])
def test_default_uses_current_python_and_explicit_binary_is_preserved(tmp_path, monkeypatch, binary, module_launch):
    import sys
    from types import SimpleNamespace
    output = tmp_path / "result.pqr"
    def execute(command, **kwargs):
        expected = [sys.executable, "-m", "pdb2pqr"] if module_launch else [binary]
        assert command[:len(expected)] == expected
        output.write_text("synthetic PQR")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(module.subprocess, "run", execute)
    assert module.run_pdb2pqr(binary, tmp_path / "input.pdb", output, 7.0, 30)[1] == "synthetic PQR"


def test_python_module_in_dependency_target_is_visible_to_subprocess(tmp_path, monkeypatch):
    package = tmp_path / "target/pdb2pqr"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "__main__.py").write_text("import sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text('target PQR')\n")
    monkeypatch.syspath_prepend(str(package.parent))
    output = tmp_path / "target.pqr"
    assert module.run_pdb2pqr("pdb2pqr30", tmp_path / "input.pdb", output, 7.0, 30)[1] == "target PQR"
