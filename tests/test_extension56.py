"""Hand checks for 0.63 cross-correlation, sign, and BDS tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.bds_test import BdsTestStep
from src.task.step.steps.cross_correlation import CrossCorrelationStep
from src.task.step.steps.difference_sign import DifferenceSignStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _series(values, name="value"):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {name: 0}},
    )


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_cross_correlation_matches_r():
    result, out = _run(
        CrossCorrelationStep(),
        {"first_label": "x", "second_label": "y", "lags": 3},
        [_series([1, 2, 3, 4, 5, 4, 3, 2, 1], "x"), _series([2, 1, 2, 4, 5, 6, 5, 8, 7], "y")],
    )
    assert out.data.shape == (7, 3)
    assert [float(out.data[i, 0]) for i in range(7)] == pytest.approx(
        [
            0.46271424434198255,
            0.4797494951287023,
            0.43048539150224246,
            0.07044306406400333,
            -0.31952605529685163,
            -0.47744743421157804,
            -0.6312251034754807,
        ],
        rel=1e-6,
    )
    assert result["n"] == 9
    assert [item["lag"] for item in result["ccf"]] == [-3, -2, -1, 0, 1, 2, 3]


def test_difference_sign_matches_r():
    result, out = _run(
        DifferenceSignStep(),
        {"value_label": "value"},
        [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])],
    )
    assert out.data.shape == (5, 1)
    assert float(out.data[0, 0]) == pytest.approx(1.4411533842457842, rel=1e-6)
    assert float(out.data[1, 0]) == pytest.approx(0.14954135458461512, rel=1e-6)
    assert result["n"] == 12
    assert result["positive"] == 7
    assert result["zeros"] == 0


def test_bds_matches_statsmodels():
    _, out = _run(BdsTestStep(), {"value_label": "value", "max_dim": 2, "epsilon": 0.5}, [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])])
    assert out.data.shape == (1, 2)
    assert float(out.data[0, 0]) == pytest.approx(4.940627273908729, rel=1e-6)
    assert float(out.data[0, 1]) == pytest.approx(7.787164227744485e-07, rel=1e-6)

    _, out = _run(BdsTestStep(), {"value_label": "value", "max_dim": 3, "epsilon": 0.5}, [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])])
    assert out.data.shape == (2, 2)
    assert float(out.data[1, 0]) == pytest.approx(21.2503127757503, rel=1e-6)
    assert float(out.data[1, 1]) == pytest.approx(3.274769415614057e-100, rel=1e-6)


def test_063_invalid_inputs():
    with pytest.raises(StepError, match="lags must be less than n"):
        _run(
            CrossCorrelationStep(),
            {"first_label": "x", "second_label": "y", "lags": 9},
            [_series([1, 2, 3, 4, 5, 6, 7, 8, 9], "x"), _series([2, 1, 2, 4, 5, 6, 5, 8, 7], "y")],
        )
    with pytest.raises(StepError, match="at least two non-zero"):
        _run(DifferenceSignStep(), {"value_label": "value"}, [_series([1, 1, 1, 1, 1])])
    with pytest.raises(StepError, match="no variation"):
        _run(BdsTestStep(), {"value_label": "value"}, [_series([1, 1, 1, 1, 1])])
