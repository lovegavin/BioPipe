"""sequence_rna_accessibility: ensemble unpaired probabilities."""

import sys
import types

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_rna_accessibility import accessibility_rows


def test_accessibility_rows():
    matrix = np.zeros((6, 6))
    matrix[0, 5] = matrix[5, 0] = 1.0
    unpaired, segments = accessibility_rows(matrix, threshold=0.5, min_length=2)
    assert unpaired.tolist() == [0.0, 1.0, 1.0, 1.0, 1.0, 0.0]
    assert segments == [{"start": 2, "end": 5, "length": 4, "mean_unpaired": 1.0}]
    with pytest.raises(StepError, match="threshold must be in"):
        accessibility_rows(matrix, threshold=2.0)


def test_pair_probability_identity():
    pytest.importorskip("RNA")
    from src.task.step.steps.sequence_rna_accessibility import pairing_probabilities

    matrix, energy, structure = pairing_probabilities("GGGAAACCC")
    assert matrix.shape == (9, 9)
    assert np.allclose(matrix, matrix.T)
    assert np.all(matrix >= 0) and np.all(matrix <= 1)
    assert energy < 0
    assert matrix.sum() >= 1.0


def _install_rna_stub(monkeypatch):
    class _Compound:
        def __init__(self, sequence, parameters=None):
            self.sequence = sequence
            self.temperature = getattr(parameters, "temperature", 37.0)

        def pf(self):
            return None

        def bpp(self):
            size = len(self.sequence)
            return [[1.0 if i == 1 and j == size else 0.0 for j in range(size + 1)] for i in range(size + 1)]

        def mfe(self):
            return "." * len(self.sequence), -1.5

    class _Parameters:
        temperature = 37.0

    module = types.ModuleType("RNA")
    module.fold_compound = _Compound
    module.md = _Parameters
    monkeypatch.setitem(sys.modules, "RNA", module)


def test_run_round_trip(monkeypatch, tmp_path):
    _install_rna_stub(monkeypatch)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences(["GGGAAACCC"], "sequence", "position", "rna")
    run(ctx, [{"name": "sequence_rna_accessibility", "inputs": ["sequence"], "params": {"output": "acc", "threshold": 0.5, "min_length": 2}}])
    result = ctx["acc"]
    assert result.dims == ["position", "statistic"]
    assert result.data.shape == (9, 2)
    assert result.data[0, 0] == pytest.approx(0.0)
    assert result.data[4, 0] == pytest.approx(1.0)
    assert result.info["mfe_energy_kcal"] == pytest.approx(-1.5)


def test_errors(monkeypatch, tmp_path):
    _install_rna_stub(monkeypatch)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences(["GGGAAACCC", "AAAA"], "sequence", "position", "rna")
    with pytest.raises(StepError, match="exactly one sequence"):
        run(ctx, [{"name": "sequence_rna_accessibility", "inputs": ["sequence"], "params": {"output": "acc"}}])
    ctx2 = Context(str(tmp_path / "task2"), {"params": {}})
    ctx2["sequence"] = encode_sequences(["GGGA"], "sequence", "position", "rna")
    with pytest.raises((StepError, ValueError)):
        run(ctx2, [{"name": "sequence_rna_accessibility", "inputs": ["sequence"], "params": {"output": "acc", "threshold": 2.0}}])
