"""Hand checks for the 0.54 Goldfeld-Quandt and Rainbow tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.goldfeld_quandt import GoldfeldQuandtStep
from src.task.step.steps.rainbow_test import RainbowTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(x, y):
    n = len(x)
    data = np.column_stack((x, y))
    form = Form(
        np.asarray(data, dtype=np.float64),
        ["sample", "variable"],
        {
            "sample": {f"s{i}": i for i in range(n)},
            "variable": {"x": 0, "y": 1},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _gq_data():
    x = np.arange(1, 21, dtype=float)
    y = np.array(
        [2, 4, 1, 6, 3, 8, 5, 10, 7, 12, 20, 15, 25, 18, 30, 22, 35, 25, 40, 28],
        dtype=float,
    )
    return x, y


def _rainbow_data():
    x = np.arange(1, 21, dtype=float)
    y = 1.0 + 0.5 * x + 4.0 * np.sin(np.pi * x / 10.0)
    return x, y


def test_goldfeld_quandt_matches_r():
    x, y = _gq_data()
    result, out = _run(
        GoldfeldQuandtStep(),
        {"response": "y", "regressor": "x"},
        [_form(x, y)],
    )
    assert out.data.shape == (7, 1)
    assert out.data[0, 0] == pytest.approx(7.8091706001348626, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(8.0)
    assert out.data[2, 0] == pytest.approx(8.0)
    assert out.data[3, 0] == pytest.approx(0.0043735156064267696, rel=1e-6)
    assert result["segment1_n"] == 10
    assert result["segment2_n"] == 10


def test_goldfeld_quandt_less_alternative():
    x, y = _gq_data()
    result, out = _run(
        GoldfeldQuandtStep(),
        {"response": "y", "regressor": "x", "alternative": "less"},
        [_form(x, y)],
    )
    assert out.data[0, 0] == pytest.approx(7.8091706001348626, rel=1e-6)
    assert out.data[3, 0] == pytest.approx(0.9956264843935732, rel=1e-6)
    assert result["alternative"] == "less"


def test_rainbow_matches_r():
    x, y = _rainbow_data()
    result, out = _run(
        RainbowTestStep(),
        {"response": "y", "regressor": "x"},
        [_form(x, y)],
    )
    assert out.data.shape == (8, 1)
    assert out.data[0, 0] == pytest.approx(37.09507275139439, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(10.0)
    assert out.data[2, 0] == pytest.approx(8.0)
    assert out.data[3, 0] == pytest.approx(1.298882331413825e-05, rel=1e-4)
    assert result["from"] == 6
    assert result["to"] == 15


def test_rejects_invalid_segments():
    x, y = _gq_data()
    with pytest.raises(StepError, match="fraction"):
        _run(
            GoldfeldQuandtStep(),
            {"response": "y", "regressor": "x", "fraction": 0.8},
            [_form(x, y)],
        )
    with pytest.raises(StepError, match="different"):
        _run(
            RainbowTestStep(),
            {"response": "x", "regressor": "x"},
            [_form(x, y)],
        )
