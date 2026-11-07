"""esm3_inverse_folding: ESM-3 backbone-conditioned sequence design."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm3_inverse_folding import (
    chain_pdb,
    design_rows,
    native_sequence,
    recovery,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


class _FakeProtein:
    def __init__(self, sequence=None):
        self.sequence = sequence


class _FakeModel:
    def generate(self, protein, config):
        return _FakeProtein(sequence="MKVLAAGIVGLLLA")

    def eval(self):
        return self

    def float(self):
        return self


def test_recovery_and_rows():
    assert recovery("ACDE", "ACDF") == pytest.approx(0.75)
    assert np.isnan(recovery("ACD", "ACDE"))
    rows = design_rows(["ACDE"], "ACDF")
    assert rows[0]["recovery"] == pytest.approx(0.75)


def test_chain_pdb_and_native(tmp_path):
    path, _ = chain_pdb(FIXTURES / "vhh_1mel.pdb", "A", tmp_path)
    lines = path.read_text().splitlines()
    assert all(line[21].strip() == "A" for line in lines[1:] if line.startswith("ATOM"))
    sequence = native_sequence(lines)
    assert len(sequence) > 100
    assert sequence.startswith("V")


def _install_esm_stub(monkeypatch):
    """Provide esm, esm.sdk and esm.sdk.api modules for platforms without esm."""

    import sys
    import types

    class _ESMProtein:
        def __init__(self, sequence=None):
            self.sequence = sequence

        @classmethod
        def from_pdb(cls, path):
            return cls(sequence="X")

    class _Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    api = types.ModuleType("esm.sdk.api")
    api.ESMProtein = _ESMProtein
    api.GenerationConfig = _Config
    sdk = types.ModuleType("esm.sdk")
    package = types.ModuleType("esm")
    package.sdk = sdk
    monkeypatch.setitem(sys.modules, "esm", package)
    monkeypatch.setitem(sys.modules, "esm.sdk", sdk)
    monkeypatch.setitem(sys.modules, "esm.sdk.api", api)
    return _ESMProtein, _Config


def test_run_round_trip(monkeypatch, tmp_path):
    import src.task.step.steps.esm3_inverse_folding as module

    monkeypatch.setattr(module, "load_model", lambda name, device: _FakeModel())
    _install_esm_stub(monkeypatch)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "esm3_inverse_folding", "params": {"output": "designs", "structure_path": str(FIXTURES / "vhh_1mel.pdb"), "chain": "A", "num_steps": 2}}])
    table = ctx["designs"]
    assert table.data.shape == (1, 2)
    assert table.info["sequences"] == ["MKVLAAGIVGLLLA"]
    assert table.info["n_residues"] == 14


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "esm3_inverse_folding", "params": {"output": "designs", "structure_path": str(tmp_path / "missing.pdb")}}])
    with pytest.raises(StepError, match="must name a .pdb"):
        (tmp_path / "x.txt").write_text("x")
        run(ctx, [{"name": "esm3_inverse_folding", "params": {"output": "designs", "structure_path": str(tmp_path / "x.txt")}}])
    with pytest.raises(StepError, match="chain 'Z' was not found"):
        chain_pdb(FIXTURES / "vhh_1mel.pdb", "Z", tmp_path)


def test_real_inverse_folding():
    import os

    if os.environ.get("OPERON_ESM3_REAL") != "1":
        pytest.skip("set OPERON_ESM3_REAL=1 to run the real ESM-3 check")
    pytest.importorskip("esm")
    import src.task.step.steps.esm3_inverse_folding as module

    module._CACHE.clear()
    ctx = Context("/tmp/operon_esm3_if", {"params": {}})
    run(ctx, [{"name": "esm3_inverse_folding", "params": {"output": "designs", "structure_path": str(FIXTURES / "vhh_1mel.pdb"), "chain": "A", "num_steps": 10, "temperature": 0.7}}])
    table = ctx["designs"]
    assert table.data.shape[0] == 1
    assert table.info["n_residues"] > 100
    assert 0.1 <= table.info["recovery"] <= 1.0
