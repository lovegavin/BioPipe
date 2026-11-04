"""Extension tests for the sequence complexity operator."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_complexity import (
    SequenceComplexityStep,
    complexity_row,
    linguistic_complexity,
    low_complexity_fraction,
    shannon_entropy,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params, sequences):
    form = encode_sequences(sequences, "sequence", "position", "protein")
    step = SequenceComplexityStep()
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_shannon_entropy_of_hand_sequences():
    assert shannon_entropy("AAAA", 1) == pytest.approx(0.0, abs=1e-9)
    assert shannon_entropy("ACGT", 1) == pytest.approx(2.0, abs=1e-9)
    assert shannon_entropy("ACGTACGT", 2) == pytest.approx(1.9502120649, abs=1e-9)
    assert math.isnan(shannon_entropy("", 1))
    assert math.isnan(shannon_entropy("AC", 3))


def test_linguistic_complexity_small_example():
    value = linguistic_complexity("ACGTACGT", 3)
    assert value == pytest.approx((4 / 8 + 4 / 7 + 4 / 6) / 3, abs=1e-6)
    assert linguistic_complexity("AAAAAAAA", 3) == pytest.approx((1 / 8 + 1 / 7 + 1 / 6) / 3, abs=1e-9)


def test_low_complexity_fraction():
    assert low_complexity_fraction("AAAAAAAAAA", 20, 2.0) == 1.0
    assert low_complexity_fraction("ACDEFGHIKLMNPQRSTVWY", 20, 2.0) == 0.0
    assert low_complexity_fraction("AAAAAAAAAAGGGGGGGGGG", 10, 1.0) == 1.0


def test_complexity_row_values():
    row = complexity_row("ACGTACGT", window=4, threshold=1.0)
    assert row["length"] == 8
    assert row["entropy_1"] == pytest.approx(2.0, abs=1e-9)
    assert row["entropy_2"] == pytest.approx(1.9502120649, abs=1e-9)
    assert row["entropy_3"] == pytest.approx(1.9182958341, abs=1e-9)
    assert row["normalized_entropy_3"] == pytest.approx(0.1479506208, abs=1e-9)
    assert row["low_complexity_fraction"] == 0.0


def test_step_profiles_three_sequences():
    sequences = ["ACDEFGHIKLMNPQRSTVWY", "AAAAAAAAGGGGGGGG", "MKWVTFISLLFLFSSAYSRGVFRR"]
    out, export = _run({}, sequences)
    assert out.data.shape == (3, 7)
    assert list(out.labels["statistic"]) == [
        "length",
        "entropy_1",
        "entropy_2",
        "entropy_3",
        "normalized_entropy_3",
        "linguistic_complexity",
        "low_complexity_fraction",
    ]
    np.testing.assert_allclose(out.data[0, 0], 20.0)
    np.testing.assert_allclose(out.data[0, 1], math.log2(20), rtol=1e-6)
    np.testing.assert_allclose(out.data[1, 1], 1.0, rtol=1e-6)
    np.testing.assert_allclose(out.data[1, 6], 1.0, rtol=1e-6)
    np.testing.assert_allclose(out.data[0, 6], 0.0, rtol=1e-6)
    assert out.info["n_sequences"] == 3
    assert export["n_sequences"] == 3


def test_parameter_and_input_errors():
    for params, message in [
        ({"window": 3}, "window must be between 5 and 200"),
        ({"window": 500}, "window must be between 5 and 200"),
        ({"low_complexity_entropy": 5.0}, "low_complexity_entropy"),
    ]:
        with pytest.raises(StepError, match=message):
            _run(params, ["ACDEFG"])

    step = SequenceComplexityStep()
    wrong_dims = Form(
        data=np.zeros((2, 3), dtype=np.float32), dims=["sample", "feature"], labels={}
    )
    with pytest.raises(StepError, match="sequence form with dims"):
        step.run(Ctx({"output": "out"}), [wrong_dims])

    no_rows = Form(
        data=np.zeros((0, 0), dtype=np.float32),
        dims=["sequence", "position"],
        labels={"sequence": {}, "position": {}},
    )
    with pytest.raises(StepError, match="not a sequence_codes Form"):
        step.run(Ctx({"output": "out"}), [no_rows])
