"""Tests for the tandem repeat finder operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_repeat_finder import SequenceRepeatFinderStep, repeat_rows


def _form(sequences, alphabet="DNA"):
    return encode_sequences(list(sequences), "sequence", "position", alphabet)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "repeats", **params}
        self.metadata = {}


def _run(params, sequences, *, output="repeats", alphabet="DNA"):
    step = SequenceRepeatFinderStep()
    ctx = Ctx({**params, "output": output})
    step.run(ctx, [_form(sequences, alphabet)])
    return ctx[output], step.export(ctx)


def test_repeat_rows_basic() -> None:
    assert repeat_rows("ATATAT") == [(1, 2, 3, 6)]
    assert repeat_rows("ACGTACGTACGT") == [(1, 4, 3, 12)]
    assert repeat_rows("ACGTACGTAA") == [(1, 4, 2, 8)]
    assert repeat_rows("ACGT") == []


def test_repeat_rows_period_bounds() -> None:
    assert repeat_rows("AAAA", min_period=1) == [(1, 1, 4, 4)]
    assert repeat_rows("ACACAC", min_period=3, max_period=4) == []
    assert repeat_rows("ATATATAT", min_copies=4) == [(1, 2, 4, 8)]


def test_step_output_labels() -> None:
    out, export = _run({}, ["ATATAT", "ACGT"])
    assert out.data.tolist() == [[1.0, 2.0, 3.0, 6.0]]
    assert list(out.labels["repeat"]) == ["seq1:1"]
    assert list(out.labels["statistic"]) == ["start", "period", "copies", "length"]
    assert export["n_sequences"] == 2
    assert out.info["n_repeats"] == 1


def test_no_repeat_gives_empty_form() -> None:
    out, export = _run({}, ["ACGTTGCA"])
    assert out.data.shape == (0, 4)
    assert export["n_repeats"] == 0


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="min_copies"):
        _run({"min_copies": 1}, ["ATATAT"])
    with pytest.raises(StepError, match="max_period"):
        _run({"min_period": 4, "max_period": 2}, ["ATATAT"])
    with pytest.raises(StepError, match="min_period"):
        _run({"min_period": 0}, ["ATATAT"])
    with pytest.raises(StepError, match="non-nucleotide"):
        _run({}, ["MKW"], alphabet="protein")
    with pytest.raises(StepError, match="dims"):
        _run({"sequence_dim": "reads"}, ["ATATAT"])
