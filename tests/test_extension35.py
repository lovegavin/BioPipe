"""Hand checks for the 0.42 normality and extreme-reaction tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.lillie_test import LillieTestStep
from src.task.step.steps.moses_test import MosesTestStep
from src.task.step.steps.shapiro_wilk import ShapiroWilkStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
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


def _sf_values():
    return [
        2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
        18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
    ]


def _moses_frame():
    values = np.array([10, 12, 14, 15, 16, 18, 20, 22, 24, 26, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11], dtype=float)
    groups = np.r_[np.zeros(10), np.ones(10)]
    return _form(
        np.column_stack([values, groups]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {"value": 0, "g": 1},
        },
    )


def test_shapiro_wilk_matches_r():
    result, out = _run(ShapiroWilkStep(), {"value_label": "x"}, [_series(_sf_values())])
    assert result["W"] == pytest.approx(0.96016416316107545, rel=1e-7)
    assert result["p"] == pytest.approx(0.54713405582814623, rel=1e-6)
    assert result["n"] == 20
    assert out.data.shape == (3, 1)


def test_lillie_matches_r():
    result, out = _run(LillieTestStep(), {"value_label": "x"}, [_series(_sf_values())])
    assert result["D"] == pytest.approx(0.081749071087235753, rel=1e-7)
    assert result["p"] == pytest.approx(0.97813612285642071, rel=1e-7)
    assert result["n"] == 20
    assert out.data.shape == (3, 1)


def test_moses_matches_r():
    result, out = _run(MosesTestStep(), {
        "value_label": "value", "group_label": "g", "group_a": "0", "group_b": "1",
    }, [_moses_frame()])
    assert result["S"] == 8
    assert result["p"] == pytest.approx(0.0015479876160990713, rel=1e-12)
    assert result["n_a"] == 10
    assert result["n_b"] == 10
    assert result["extreme"] == 1
    assert out.data.shape == (5, 1)


def test_042_rejects_invalid_inputs():
    with pytest.raises(StepError, match="between 3 and 5000"):
        _run(ShapiroWilkStep(), {"value_label": "x"}, [_series([1.0, 2.0])])
    with pytest.raises(StepError, match="at least 5"):
        _run(LillieTestStep(), {"value_label": "x"}, [_series([1.0, 2.0, 3.0, 4.0])])
    with pytest.raises(StepError, match="each group"):
        _run(MosesTestStep(), {
            "value_label": "value", "group_label": "g", "group_a": "0", "group_b": "1",
        }, [_form(
            np.column_stack([np.arange(6.0), np.zeros(6)]),
            ["sample", "feature"],
            {"sample": {f"s{i}": i for i in range(6)}, "feature": {"value": 0, "g": 1}},
        )])
