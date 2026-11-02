"""sequence_aggregation_propensity: a3v hotspots."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_aggregation_propensity import hotspot_segments, propensity_scores, window_scores


def test_scores_and_windows():
    assert propensity_scores("VI") == pytest.approx([0.671, 0.853])
    assert window_scores(propensity_scores("VI"), 2) == pytest.approx([0.762])


def test_hotspots_hand_case():
    scores = propensity_scores("VVVVV")
    hotspots = hotspot_segments(scores, window=5, threshold=0.35, min_length=3)
    assert [(h["start"], h["end"], h["length"]) for h in hotspots] == [(1, 5, 5)]
    assert hotspots[0]["mean_score"] == pytest.approx(0.671)


def test_run_writes_table():
    form = encode_sequences(["VVVVV"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp281", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_aggregation_propensity", "inputs": ["sequence"], "params": {"output": "hotspots", "window": 5}}])
    result = ctx["hotspots"]
    assert result.dims == ["hotspot", "statistic"]
    assert result.info["n_hotspots"] == 1


def test_errors():
    assert hotspot_segments(propensity_scores("DDDDD"), window=5, threshold=0.35, min_length=3) == []
    with pytest.raises(StepError, match="outside the a3v scale"):
        propensity_scores("X")
