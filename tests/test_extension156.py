"""Tests for the sequence hydrophobicity profile operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_hydrophobicity_profile import (
    SequenceHydrophobicityProfileStep,
    hydrophobic_segments,
    window_profile,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params, sequences):
    ctx = Ctx(params)
    form = encode_sequences(sequences, "sequence", "position", "protein")
    step.run(ctx, [form])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_window_profile_hand_computed():
    # All alanine: every window mean equals 1.8.
    values = window_profile("AAAAAAAAA", 3)
    assert np.allclose(values[1:8], 1.8)
    assert np.isnan(values[0]) and np.isnan(values[8])


def test_window_profile_mixed_window():
    # Window 3 over "AVV": (1.8 + 4.2 + 4.2) / 3 = 3.4
    values = window_profile("AVVV", 3)
    assert np.isclose(values[1], (1.8 + 4.2 + 4.2) / 3)
    assert np.isclose(values[2], (4.2 + 4.2 + 4.2) / 3)


def test_window_profile_unknown_residue_raises():
    with pytest.raises(StepError, match="outside the Kyte-Doolittle scale"):
        window_profile("AXA", 3)


def test_hydrophobic_segments():
    profile = np.array([np.nan, 2.0, 2.5, 0.1, 3.0, np.nan])
    assert hydrophobic_segments(profile, 1.6) == [(2, 3), (5, 5)]


def test_step_output_and_export():
    out, export = _run(
        SequenceHydrophobicityProfileStep(),
        {"window": 3, "threshold": 2.0},
        ["AVVVLMK", "GGGGGGG"],
    )
    assert list(out.dims) == ["sequence", "position"]
    assert out.data.shape == (2, 7)
    assert np.isnan(out.data[0, 0]) and np.isnan(out.data[0, 6])
    assert np.isclose(out.data[0, 3], (4.2 + 4.2 + 3.8) / 3)
    assert np.isnan(out.data[1, 0])
    assert np.isclose(out.data[1, 3], -0.4)
    assert out.labels["sequence"] == {"seq1": 0, "seq2": 1}
    assert out.labels["position"]["7"] == 6
    assert out.info["window"] == 3
    assert out.info["scale"] == "kyte-doolittle"
    assert out.info["sequences"][0]["segments"] == [[2, 5]]
    assert export["n_sequences"] == 2


def test_step_matches_biopython_gravy():
    protein = pytest.importorskip("Bio.SeqUtils.ProtParam")
    sequence = "MKWVTFISLLFLFSSAYSRGVFRR"
    per_residue = window_profile(sequence, 1)
    expected = protein.ProteinAnalysis(sequence).gravy()
    assert np.isclose(float(per_residue.mean()), expected)
    out, _ = _run(SequenceHydrophobicityProfileStep(), {"window": 9}, [sequence])
    finite = out.data[0][np.isfinite(out.data[0])]
    assert finite.size == len(sequence) - 8


def test_step_parameter_errors():
    with pytest.raises(StepError, match="window must be at least 3"):
        _run(SequenceHydrophobicityProfileStep(), {"window": 1}, ["ACDEF"])
    with pytest.raises(StepError, match="odd number"):
        _run(SequenceHydrophobicityProfileStep(), {"window": 4}, ["ACDEF"])
    with pytest.raises(StepError, match="at least as long as"):
        _run(SequenceHydrophobicityProfileStep(), {"window": 9}, ["ACD"])
    with pytest.raises(StepError, match="contains no sequence"):
        _run(SequenceHydrophobicityProfileStep(), {}, [])
