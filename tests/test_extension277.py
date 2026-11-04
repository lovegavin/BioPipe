"""sequence_disorder_predictor: windowed disorder segments."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_disorder_predictor import (
    disorder_segments,
    residue_scores,
    window_mean,
)


def test_residue_scores_and_window_mean():
    assert list(residue_scores("RKW")) == [1.0, 1.0, -1.0]
    assert window_mean(np.array([1.0, 1.0, 1.0]), 3) == pytest.approx([1.0])
    assert window_mean(np.array([1.0, 0.0, -1.0]), 2) == pytest.approx([0.5, -0.5])


def test_disorder_segments_hand_case():
    scores = residue_scores("KKKKK" + "WWWWW")
    segments = disorder_segments(scores, window=5, threshold=0.0, min_length=4)
    assert len(segments) == 1
    assert (segments[0]["start"], segments[0]["end"], segments[0]["length"]) == (1, 7, 7)
    assert segments[0]["mean_score"] == pytest.approx(3 / 7)


def test_disorder_segments_threshold_and_min_length():
    scores = residue_scores("KKKKK" + "WWWWW")
    high = disorder_segments(scores, window=5, threshold=0.9, min_length=4)
    assert [(s["start"], s["end"], s["length"]) for s in high] == [(1, 5, 5)]
    assert disorder_segments(scores, window=5, threshold=0.0, min_length=20) == []


def test_run_writes_disorder_table():
    import tempfile

    form = encode_sequences(["KKKKK" + "WWWWW"], "sequence", "position", "protein")
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_disorder_predictor", "inputs": ["sequence"], "params": {"output": "disorder", "window": 5}}])
    result = ctx["disorder"]
    assert result.dims == ["segment", "statistic"]
    assert result.info["n_segments"] == 1


def test_errors():
    with pytest.raises(StepError, match="shorter than the window"):
        disorder_segments(residue_scores("KKK"), window=5, threshold=0.0, min_length=1)
    assert disorder_segments(residue_scores("WWWWWWWW"), window=5, threshold=0.0, min_length=4) == []
