"""esm3_fold: ESM-3 sequence-to-structure prediction."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm3_fold import fold_sequence

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

_PDB = """HEADER    TEST
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 80.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00 80.00           C
ATOM      3  C   ALA A   1       2.000   1.000   0.000  1.00 80.00           C
ATOM      4  O   ALA A   1       3.000   1.000   0.000  1.00 80.00           O
END
"""


class _FakeProtein:
    def __init__(self):
        self.coordinates = np.zeros((2, 3))
        self.plddt = np.array([80.0, 80.0])
        self.ptm = 0.5

    def to_pdb(self, path):
        Path(path).write_text(_PDB)


class _FakeModel:
    def generate(self, protein, config):
        return _FakeProtein()


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


def test_fold_sequence_writes_pdb(monkeypatch):
    _install_esm_stub(monkeypatch)
    result, path = fold_sequence(_FakeModel(), "AC", num_steps=2)
    assert path.is_file()
    assert "ATOM" in path.read_text()
    assert result.plddt.mean() == pytest.approx(80.0)


def test_run_round_trip(monkeypatch, tmp_path):
    import src.task.step.steps.esm3_fold as module

    monkeypatch.setattr(module, "load_model", lambda name, device: _FakeModel())
    _install_esm_stub(monkeypatch)
    form = encode_sequences(["AC"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "esm3_fold", "inputs": ["sequence"], "params": {"output": "structure", "num_steps": 2}}])
    table = ctx["structure"]
    assert table.data.shape[0] == 4
    assert table.dims == ["atom", "field"]


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="exactly one sequence"):
        form = encode_sequences(["AC", "AD"], "sequence", "position", "protein")
        ctx["sequence"] = form
        run(ctx, [{"name": "esm3_fold", "inputs": ["sequence"], "params": {"output": "structure"}}])


def test_real_fold():
    import os

    if os.environ.get("OPERON_ESM3_REAL") != "1":
        pytest.skip("set OPERON_ESM3_REAL=1 to run the real ESM-3 check")
    pytest.importorskip("esm")
    lines = (FIXTURES / "vhh_1mel.pdb").read_text().splitlines()
    sequence = []
    seen = set()
    table = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V"}
    for line in lines:
        if not line.startswith("ATOM") or line[21].strip() != "A":
            continue
        key = int(line[22:26])
        if key in seen:
            continue
        seen.add(key)
        sequence.append(table.get(line[17:20].strip(), "X"))
    sequence = "".join(sequence)
    ctx = Context("/tmp/operon_esm3_fold", {"params": {}})
    ctx["sequence"] = encode_sequences([sequence], "sequence", "position", "protein")
    run(ctx, [{"name": "esm3_fold", "inputs": ["sequence"], "params": {"output": "structure", "num_steps": 10}}])
    result = ctx["structure"]
    assert result.data.shape[0] > 100
    assert result.info["mean_plddt"] > 0.3
