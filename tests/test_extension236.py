"""Tests for the transmembrane-segment operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_hydrophobicity_profile import KYTE_DOOLITTLE
from src.task.step.steps.sequence_tm_segments import (
    hydropathy_scores,
    tm_segments,
    window_means,
)


def _segments(sequence: str, *, window: int = 19, threshold: float = 1.6, min_length: int = 12):
    return tm_segments(
        hydropathy_scores(sequence),
        window=window,
        threshold=threshold,
        min_length=min_length,
    )


def test_hydropathy_scores_follow_the_kyte_doolittle_scale() -> None:
    assert hydropathy_scores("ALV") == pytest.approx([1.8, 3.8, 4.2])
    assert hydropathy_scores("L")[0] == KYTE_DOOLITTLE["L"] == 3.8
    with pytest.raises(StepError, match="residues outside the Kyte-Doolittle scale: B"):
        hydropathy_scores("ALB")


def test_window_means() -> None:
    assert window_means(np.array([1.0, 2.0, 3.0, 4.0]), 2) == pytest.approx(
        [1.5, 2.5, 3.5]
    )
    assert window_means(np.array([1.0, 2.0]), 3).size == 0


def test_one_long_hydrophobic_stretch() -> None:
    records = _segments("L" * 30)
    assert len(records) == 1
    record = records[0]
    assert record["start"] == 1
    assert record["end"] == 30
    assert record["length"] == 30
    assert record["mean_hydropathy"] == pytest.approx(3.8)
    assert record["max_hydropathy"] == pytest.approx(3.8)


def test_threshold_and_min_length_filter_segments() -> None:
    assert _segments("L" * 30, threshold=4.0) == []
    assert _segments("L" * 30, min_length=31) == []
    assert _segments("L" * 30, min_length=5) != []


def test_hydrophilic_sequence_has_no_segment() -> None:
    assert _segments("D" * 40) == []


def test_multiple_spans_are_ordered_and_disjoint() -> None:
    sequence = "L" * 30 + "D" * 10 + "L" * 30
    records = _segments(sequence)
    assert len(records) == 2
    starts = [record["start"] for record in records]
    assert starts == sorted(starts)
    for record in records:
        assert record["length"] == record["end"] - record["start"] + 1
        assert record["length"] >= 12
        span = sequence[record["start"] - 1 : record["end"]]
        assert span.count("L") > span.count("D")


def test_runner_round_trip(tmp_path) -> None:
    ctx = Context(str(tmp_path / "tm"), {"params": {}})
    ctx["proteins"] = encode_sequences(["L" * 30, "D" * 30], "sequence", "position", "protein")
    run(
        ctx,
        [
            {
                "name": "sequence_tm_segments",
                "inputs": ["proteins"],
                "params": {"output": "segments"},
            }
        ],
    )
    form = ctx["segments"]
    assert form.dims == ["segment", "statistic"]
    assert form.data.shape == (1, 5)
    assert form.data[0] == pytest.approx([1.0, 30.0, 30.0, 3.8, 3.8])
    assert set(form.labels["segment"]) == {"seq1:tm1"}
    assert form.info["window"] == 19
    assert form.info["n_segments"] == 1
    exports = sorted((tmp_path / "tm").rglob("*sequence_tm_segments*.json"))
    assert exports


def test_runner_validation_errors(tmp_path) -> None:
    ctx = Context(str(tmp_path / "bad"), {"params": {}})

    def _call(sequences, **params) -> None:
        local = Context(str(tmp_path / "bad"), {"params": {}})
        local["proteins"] = encode_sequences(sequences, "sequence", "position", "protein")
        run(
            local,
            [
                {
                    "name": "sequence_tm_segments",
                    "inputs": ["proteins"],
                    "params": {"output": "segments", **params},
                }
            ],
        )

    with pytest.raises((StepError, ValueError), match="window"):
        _call(["L" * 30], window=20)
    with pytest.raises((StepError, ValueError), match="threshold"):
        _call(["L" * 30], threshold=6.0)
    with pytest.raises((StepError, ValueError), match="min_length"):
        _call(["L" * 30], min_length=3)
    with pytest.raises(StepError, match="shorter than the window"):
        _call(["L" * 10])
    with pytest.raises(StepError, match="no transmembrane segment reaches"):
        _call(["D" * 30])
