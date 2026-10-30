"""Hand tests for the 0.25 regression/time-series diagnostics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.chow_test import ChowTestStep
from src.task.step.steps.ljung_box import LjungBoxStep
from src.task.step.steps.white_test import WhiteTestStep


X1 = np.arange(1, 21, dtype=np.float32)
X2 = np.tile(np.array([0.0, 1.0], dtype=np.float32), 10)
RESID = np.array(
    [-1, 1, -1.5, 1.5, -2, 2, -2.5, 2.5, -3, 3, -1.2, 1.2, -1.7, 1.7, -2.2, 2.2, -2.7, 2.7, -3.2, 3.2],
    dtype=np.float32,
)
Y_WHITE = (2.0 + 1.5 * X1 + 0.5 * X2 + RESID).astype(np.float32)
Y_CHOW = np.concatenate([
    1.0 + 2.0 * X1[:10] + RESID[:10],
    5.0 + 0.5 * X1[10:] + RESID[10:],
]).astype(np.float32)
SERIES = np.array([1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 8, 7, 9, 8, 10, 9, 11], dtype=np.float32)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form() -> Form:
    data = np.column_stack([Y_WHITE, Y_CHOW, X1, X1, X2, SERIES])
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {
                "y_white": 0,
                "y_chow": 1,
                "x": 2,
                "x1": 3,
                "x2": 4,
                "series": 5,
            },
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def test_white_matches_r():
    ctx = Ctx({"response_label": "y_white", "predictors": ["x1", "x2"]})
    step = WhiteTestStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["lm_statistic"] == pytest.approx(5.6138306138, rel=1e-5)
    assert out["lm_p"] == pytest.approx(0.3456253123, rel=1e-5)
    assert out["f_statistic"] == pytest.approx(1.0926275992, rel=1e-5)
    assert out["f_p"] == pytest.approx(0.4068524667, rel=1e-5)
    assert out["n"] == 20


def test_chow_matches_r():
    ctx = Ctx({"response_label": "y_chow", "predictors": ["x"], "break_fraction": 0.5})
    step = ChowTestStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["F"] == pytest.approx(25.2160566352, rel=1e-5)
    assert out["p"] == pytest.approx(0.0000113223, rel=1e-5)
    assert out["rss_pooled"] == pytest.approx(397.4351503759, rel=1e-5)
    assert out["rss1"] == pytest.approx(43.7878787879, rel=1e-5)
    assert out["rss2"] == pytest.approx(51.9333333333, rel=1e-5)
    assert out["df1"] == 2
    assert out["df2"] == 16


def test_ljung_box_matches_r():
    ctx = Ctx({"value_label": "series", "lags": 5})
    step = LjungBoxStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["Q"] == pytest.approx(37.7313478225, rel=1e-8)
    assert out["p"] == pytest.approx(4.272e-7, rel=1e-4)
    assert out["df"] == 5
    assert out["n"] == 20


def test_ljung_box_rejects_too_many_lags():
    ctx = Ctx({"value_label": "series", "lags": 20})
    with pytest.raises(StepError, match="less than n - 1"):
        LjungBoxStep().run(ctx, [_form()])


def test_chow_rejects_invalid_break():
    ctx = Ctx({"response_label": "y_chow", "predictors": ["x"], "break_fraction": 0.05})
    with pytest.raises(StepError, match="break_fraction"):
        ChowTestStep().run(ctx, [_form()])
