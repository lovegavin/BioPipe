"""Hand checks for the 0.45 exact and median tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.binomial_test import BinomialTestStep
from src.task.step.steps.boschloo_exact import BoschlooExactStep
from src.task.step.steps.mood_median_test import MoodMedianTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float32),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"x": 0},
        },
    )


def _groups():
    values = [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 5, 6, 7, 8, 9]
    groups = ["a"] * 5 + ["b"] * 5 + ["c"] * 5
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    form = _form(
        np.column_stack([values, codes]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"value": 0, "group": 1},
        },
        {"feature": {"group": encoder}},
    )
    return form


def _table():
    return _form(
        np.array([[8, 2], [1, 9]], dtype=float),
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1}, "column": {"c0": 0, "c1": 1}},
    )


def test_binomial_exact_matches_scipy():
    result, out = _run(
        BinomialTestStep(),
        {"value_label": "x", "success_value": 1, "null_probability": 0.5},
        [_series([1, 1, 1, 1, 1, 1, 1, 0, 0, 0])],
    )
    assert result["successes"] == 7
    assert result["n"] == 10
    assert result["p"] == pytest.approx(0.34375, rel=1e-6)
    assert result["ci_low"] == pytest.approx(0.3475471499399921, rel=1e-6)
    assert result["ci_high"] == pytest.approx(0.9332604888222655, rel=1e-6)
    assert out.data.shape == (7, 1)


def test_mood_median_matches_scipy():
    result, out = _run(
        MoodMedianTestStep(),
        {"value_label": "value", "group_label": "group"},
        [_groups()],
    )
    assert result["statistic"] == pytest.approx(7.8, abs=1e-6)
    assert result["p"] == pytest.approx(0.020241911445804395, rel=1e-6)
    assert result["median"] == 5
    assert result["n_groups"] == 3
    assert result["n"] == 15
    assert out.data.shape == (5, 1)


def test_boschloo_matches_scipy():
    result, out = _run(
        BoschlooExactStep(),
        {},
        [_table()],
    )
    assert result["p"] == pytest.approx(0.0018352604919337544, rel=1e-6)
    assert result["fisher_p"] == pytest.approx(0.002738747320790664, rel=1e-6)
    assert result["odds_ratio"] == pytest.approx(36.0, rel=1e-6)
    assert result["n"] == 20
    assert out.data.shape == (4, 1)


def test_045_rejects_invalid_inputs():
    with pytest.raises(StepError, match="strictly between"):
        _run(
            BinomialTestStep(),
            {"value_label": "x", "null_probability": 1.0},
            [_series([1, 0])],
        )
    with pytest.raises(StepError, match="constant"):
        _run(
            MoodMedianTestStep(),
            {"value_label": "value", "group_label": "group"},
            [
                _form(
                    np.column_stack([[1, 1, 1, 1], [0, 0, 1, 1]]),
                    ["sample", "feature"],
                    {"sample": {f"s{i}": i for i in range(4)}, "feature": {"value": 0, "group": 1}},
                )
            ],
        )
    with pytest.raises(StepError, match="integer"):
        _run(
            BoschlooExactStep(),
            {},
            [
                _form(
                    np.array([[1.5, 2], [1, 9]], dtype=float),
                    ["row", "column"],
                    {"row": {"r0": 0, "r1": 1}, "column": {"c0": 0, "c1": 1}},
                )
            ],
        )
