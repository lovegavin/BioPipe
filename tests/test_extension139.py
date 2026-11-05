"""Tests for the ESM-IF mutation scan operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_if_mutation_scan import (
    EsmIfMutationScanStep,
    mutation_rows,
    parse_positions,
)


class _Alphabet:
    def __init__(self) -> None:
        letters = "ACDEFGHIKLMNPQRSTVWY"
        self.index = {letter: position + 1 for position, letter in enumerate(letters)}

    def get_idx(self, letter: str) -> int:
        return self.index[letter]


def _log_probs(sequence: str) -> np.ndarray:
    """Deterministic per-position log probabilities over a 21-slot vocabulary."""
    alphabet = _Alphabet()
    values = np.full((len(sequence), 21), -10.0)
    for position, residue in enumerate(sequence):
        for letter, index in alphabet.index.items():
            values[position, index] = -abs(position - len(letter)) * 0.1 - 1.0
        values[position, alphabet.get_idx(residue)] = -0.5
    return values


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "mutations", **params}
        self.metadata = {}


def test_parse_positions() -> None:
    assert parse_positions("", 4) == [1, 2, 3, 4]
    assert parse_positions("3,1-2", 4) == [1, 2, 3]
    assert parse_positions("2; 4", 4) == [2, 4]
    with pytest.raises(StepError, match="is not of the form"):
        parse_positions("1-", 4)
    with pytest.raises(StepError, match="starts after it ends"):
        parse_positions("4-2", 4)
    with pytest.raises(StepError, match="is not an integer"):
        parse_positions("x", 4)
    with pytest.raises(StepError, match="outside the chain"):
        parse_positions("9", 4)
    with pytest.raises(StepError, match="selected no residue"):
        parse_positions(" , ", 4)


def test_mutation_rows_match_hand_computation() -> None:
    sequence = "ACG"
    rows = mutation_rows(sequence, _log_probs(sequence), _Alphabet(), [2])
    assert len(rows) == 19
    assert all(row[0].startswith("C2") for row in rows)
    llrs = [row[2] for row in rows]
    assert llrs == sorted(llrs, reverse=True)
    assert all(row[3] < 0.0 and row[4] <= row[3] for row in rows)
    assert sorted(row[5] for row in rows) == list(range(1, 20))
    for row in rows:
        assert row[2] == pytest.approx(row[4] - row[3], abs=1e-9)


def test_mutation_rows_cover_all_positions() -> None:
    sequence = "AC"
    rows = mutation_rows(sequence, _log_probs(sequence), _Alphabet(), [1, 2])
    assert len(rows) == 38
    assert [row[1] for row in rows].count(1) == 19
    assert [row[1] for row in rows].count(2) == 19


def test_parameter_validation() -> None:
    step = EsmIfMutationScanStep()
    step.ctx = _Ctx({"chain": "A", "model_path": ""})
    with pytest.raises(StepError, match="model_path is required"):
        step._validate()
    step.ctx = _Ctx({"chain": "", "model_path": "x.pt"})
    with pytest.raises(StepError, match="chain must name"):
        step._validate()
    step.ctx = _Ctx({"chain": "A", "model_path": "x.pt", "max_positions": 0})
    with pytest.raises(StepError, match="max_positions"):
        step._validate()


def test_pdb_dims_are_required() -> None:
    form = Form(
        data=np.zeros((2, 2), dtype=np.float32),
        dims=["atom", "value"],
        labels={"atom": {"a": 0, "b": 1}, "value": {"x": 0, "y": 1}},
    )
    step = EsmIfMutationScanStep()
    step.ctx = _Ctx({"chain": "A", "model_path": "/missing.pt"})
    with pytest.raises(StepError, match="a PDB form with dims"):
        step.run(step.ctx, [form])


def test_real_checkpoint_scan_on_fixture() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("biotite")
    esm = pytest.importorskip("esm")
    if not hasattr(esm, "pretrained"):
        pytest.skip("fair-esm is shadowed by the ESM-3 package")
    try:
        pytest.importorskip("torch_scatter")
    except OSError as exc:
        pytest.skip(f"torch_scatter is ABI-incompatible: {exc}")

    from pathlib import Path

    from src.reader import pick_reader

    checkpoint = Path("/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")
    if not checkpoint.is_file():
        pytest.skip("ESM-IF checkpoint is not available")
    fixture = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    form = pick_reader(fixture).implementation().read(
        fixture, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )
    ctx = _Ctx({"chain": "C", "model_path": str(checkpoint), "positions": "2,5"})
    step = EsmIfMutationScanStep()
    step.run(ctx, [form])
    output = ctx["mutations"]
    assert output.data.shape == (38, 4)
    assert list(output.dims) == ["mutation", "statistic"]
    assert output.info["n_positions"] == 2
    assert output.info["positions"] == [2, 5]
    assert np.all(np.isfinite(output.data))
    exported = step.export(ctx)
    assert exported["n_mutations"] == 38
    assert len(exported["top_mutations"]) == 10
    assert output.labels["statistic"] == {
        "llr": 0,
        "wt_log_prob": 1,
        "mut_log_prob": 2,
        "mutant_rank": 3,
    }
