"""Tests for the ESM-IF masked region scan operator."""

from __future__ import annotations

import contextlib
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers.pdb_reader import PdbReader
from src.task.step import steps as steps_package  # noqa: F401  (eager import for monkeypatching)
from src.task.step.steps import esm_if_masked_region_scan as module
from src.task.step.steps.esm_if_masked_region_scan import (
    EsmIfMaskedRegionScanStep,
    masked_windows,
    partial_sequence,
    window_rows,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "windows", **params}
        self.metadata = {}


def _atom(serial, name, resname, number, x, y, z):
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} A{number:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
    )


def _pdb(path: Path) -> Path:
    lines = []
    serial = 0
    for index in range(6):
        base = index * 3.8
        for offset, name in enumerate(("N", "CA", "C")):
            serial += 1
            lines.append(_atom(serial, name, "ALA", index + 1, base + offset, 0.0, 0.0))
    path.write_text("\n".join(lines) + "\n")
    return path


def _form(path: Path) -> Form:
    return PdbReader().read(path, dims=["atom", "field"], labels={}, encoders={})


class _Torch:
    @staticmethod
    def no_grad():
        return contextlib.nullcontext()

    @staticmethod
    def manual_seed(seed):
        return None


class _Model:
    def sample(self, coords, partial_seq=None, temperature=1.0):
        return "W" * len(coords)


def test_masked_windows_and_partial() -> None:
    assert masked_windows(10, 4, 3) == [(0, 4), (3, 7), (6, 10)]
    assert masked_windows(6, 3, 2) == [(0, 3), (2, 5)]
    assert partial_sequence("ACDEFG", 2, 4) == ["A", "C", "<mask>", "<mask>", "F", "G"]
    with pytest.raises(StepError, match="larger than the chain"):
        masked_windows(4, 6, 1)
    with pytest.raises(StepError, match="window must be at least"):
        masked_windows(4, 0, 1)
    with pytest.raises(StepError, match="step must be at least"):
        masked_windows(4, 2, 0)


def test_window_rows_hand_values() -> None:
    sequence = "AAAA"
    windows = [(0, 2), (2, 4)]
    scores = [np.asarray([-1.0, -1.0, -2.0, -2.0]), np.asarray([-1.0, -1.0, -2.0, -2.0])]
    rows = window_rows(sequence, ["AAAA", "AAWA"], windows, scores)
    assert rows[0] == [1.0, 2.0, 1.0, -1.0]
    assert rows[1] == [3.0, 4.0, 0.5, -2.0]


def test_step_with_fake_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(module, "load_esm_if", lambda path, operator: (_Model(), None, _Torch()))
    monkeypatch.setattr(module, "residue_log_probs", lambda model, alphabet, coords, sequence: np.full(len(sequence), -1.5))
    ctx = Ctx({"model_path": "stub.pt", "chain": "A", "window": 3, "step": 2, "temperature": 0.1, "seed": 1})
    EsmIfMaskedRegionScanStep().run(ctx, [_form(_pdb(tmp_path / "chain.pdb"))])
    out = ctx["windows"]
    assert out.data.shape == (2, 4)
    assert list(out.labels["window"]) == ["1-3", "3-5"]
    assert list(out.labels["statistic"]) == ["start", "end", "recovery", "mean_log_prob"]
    assert out.data[:, 2].tolist() == [0.0, 0.0]
    assert np.allclose(out.data[:, 3], -1.5)
    assert out.info["native_sequence"] == "AAAAAA"
    assert out.info["designs"] == ["WWWWWW", "WWWWWW"]


def test_parameter_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(module, "load_esm_if", lambda path, operator: (_Model(), None, _Torch()))
    monkeypatch.setattr(module, "residue_log_probs", lambda model, alphabet, coords, sequence: np.full(len(sequence), -1.0))
    form = _form(_pdb(tmp_path / "chain.pdb"))
    cases = [
        ({"window": 0}, "window must be between"),
        ({"step": 0}, "step must be between"),
        ({"num_samples": 0}, "num_samples must be between"),
        ({"temperature": 0.0}, "temperature must be in"),
        ({"seed": -1}, "seed must not be negative"),
        ({"window": 64}, "larger than the chain"),
        ({"chain": "Z"}, "chain 'Z' was not found"),
    ]
    for overrides, message in cases:
        ctx = Ctx({"model_path": "stub.pt", **overrides})
        with pytest.raises(StepError, match=message):
            EsmIfMaskedRegionScanStep().run(ctx, [form])


def test_dims_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(module, "load_esm_if", lambda path, operator: (_Model(), None, _Torch()))
    form = _form(_pdb(tmp_path / "chain.pdb"))
    ctx = Ctx({"model_path": "stub.pt", "atom_dim": "a"})
    with pytest.raises(StepError, match="a PDB form with dims"):
        EsmIfMaskedRegionScanStep().run(ctx, [form])
