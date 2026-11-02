"""Tests for the sliding-window GC/AT skew profile operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_gc_skew_profile import (
    SequenceGcSkewProfileStep,
    skew_windows,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "windows", **params}
        self.metadata = {}


def _form(*sequences: str) -> Form:
    return encode_sequences(list(sequences), "sequence", "position", "DNA")


def test_skew_windows_hand_computed() -> None:
    # GGGG: GC 1.0 and skew +1; CCCC: skew -1; both have no A/T.
    rows = skew_windows("GGGGCCCC", 4, 4)
    assert len(rows) == 2
    assert rows[0] == (0, 4, 1.0, 1.0, 0.0, 4)
    assert rows[1] == (4, 8, 1.0, -1.0, 0.0, 4)

    # AAAT: AT skew = (3 - 1) / 4 = 0.5 and no GC -> GC skew defined as 0.
    assert skew_windows("AAAT", 4, 4) == [(0, 4, 0.0, 0.0, 0.5, 0)]

    # ACGT: GC 0.5, GC skew 0, AT skew 0.
    assert skew_windows("ACGT", 4, 4) == [(0, 4, 0.5, 0.0, 0.0, 2)]

    # A sliding step of one over a length-3 window yields two windows:
    # GGC (GC 3/3, skew (2-1)/3) and GCA (GC 2/3, skew 0, AT skew 1.0).
    assert skew_windows("GGCA", 3, 1) == [
        (0, 3, 1.0, 1 / 3, 0.0, 3),
        (1, 4, 2 / 3, 0.0, 1.0, 2),
    ]


def test_step_writes_windows() -> None:
    form = _form("GGGGCCCC")
    step = SequenceGcSkewProfileStep()
    ctx = Ctx({"window": 4, "step": 4})
    step.run(ctx, [form])
    out = ctx["windows"]
    assert out.dims == ["window", "statistic"]
    assert list(out.labels["statistic"]) == ["gc_content", "gc_skew", "at_skew", "n_gc"]
    assert list(out.labels["window"]) == ["seq1:1-4", "seq1:5-8"]
    assert out.data.dtype == np.float32
    assert np.allclose(out.data[:, 0], [1.0, 1.0])
    assert np.allclose(out.data[:, 1], [1.0, -1.0])
    assert out.info["n_windows"] == 2
    assert out.info["window"] == 4 and out.info["step"] == 4
    assert out.info["starts"] == [1, 5] and out.info["ends"] == [4, 8]
    assert step.export(ctx)["n_windows"] == 2


def test_multiple_sequences_are_concatenated() -> None:
    ctx = Ctx({"window": 4, "step": 4})
    SequenceGcSkewProfileStep().run(ctx, [_form("GGGG", "CCCC")])
    out = ctx["windows"]
    assert list(out.labels["window"]) == ["seq1:1-4", "seq2:1-4"]
    assert np.allclose(out.data[:, 1], [1.0, -1.0])
    assert out.info["sequence_indexes"] == [1, 2]


def test_short_sequence_yields_empty_form() -> None:
    ctx = Ctx({"window": 8, "step": 4})
    SequenceGcSkewProfileStep().run(ctx, [_form("ACGT")])
    out = ctx["windows"]
    assert out.data.shape == (0, 4)
    assert out.info["n_windows"] == 0


def test_parameter_errors() -> None:
    form = _form("ACGTACGT")
    cases = [
        ({"window": 1}, "window must be an integer between"),
        ({"step": 0}, "step must be a positive integer"),
        ({"window": 4, "step": 5}, "step must be a positive integer"),
    ]
    for overrides, message in cases:
        ctx = Ctx(overrides)
        with pytest.raises(StepError, match=message):
            SequenceGcSkewProfileStep().run(ctx, [form])


def test_wrong_input_contract() -> None:
    form = _form("ACGT")
    broken = Form(
        data=form.data,
        dims=["other", "position"],
        labels={"other": form.labels["sequence"], "position": form.labels["position"]},
        info=form.info,
    )
    ctx = Ctx({})
    with pytest.raises(StepError, match="sequence input expected"):
        SequenceGcSkewProfileStep().run(ctx, [broken])


def test_empty_input_list() -> None:
    with pytest.raises(StepError, match="sequence form input is required"):
        SequenceGcSkewProfileStep().run(Ctx({}), [])
