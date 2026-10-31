"""Tests for 0.92 seasonal ARIMA."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.sarima import SarimaStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(values):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {"y": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _seasonal_series() -> np.ndarray:
    rng = np.random.default_rng(20261115)
    n = 120
    e = rng.normal(size=n)
    values = np.zeros(n, dtype=np.float64)
    for t in range(n):
        values[t] = e[t]
        if t >= 1:
            values[t] += 0.5 * e[t - 1]
        if t >= 4:
            values[t] += 0.6 * values[t - 4]
    return values


def test_sarima_matches_reference_fit():
    y = _seasonal_series()
    export = _run(
        SarimaStep(),
        {
            "value_label": "y", "p": 0, "d": 0, "q": 1,
            "P": 0, "D": 0, "Q": 1, "seasonal_period": 4, "output": "fit",
        },
        _form(y[:, None]),
    )
    assert export["terms"] == ["intercept", "ma.L1", "ma.S.L4"]
    np.testing.assert_allclose(
        export["coef"],
        [-0.08954528, 0.40081084, 0.53008793],
        atol=2e-5,
    )
    assert export["sigma2"] == pytest.approx(0.89238742, abs=2e-5)
    assert export["aic"] == pytest.approx(336.351426, abs=2e-3)
    assert export["order"] == [0, 0, 1]
    assert export["seasonal_order"] == [0, 0, 1, 4]
    assert export["n"] == 120


def test_sarima_rejects_invalid_orders_and_series():
    y = _seasonal_series()
    with pytest.raises(StepError, match="seasonal order"):
        _run(
            SarimaStep(),
            {"value_label": "y", "P": 0, "D": 0, "Q": 0},
            _form(y[:, None]),
        )
    with pytest.raises(StepError, match="constant trend"):
        _run(
            SarimaStep(),
            {
                "value_label": "y", "p": 0, "q": 1,
                "P": 0, "D": 1, "Q": 0, "seasonal_period": 4,
            },
            _form(y[:, None]),
        )
    with pytest.raises(StepError, match="seasonal_period"):
        _run(
            SarimaStep(),
            {
                "value_label": "y", "p": 0, "q": 1,
                "P": 0, "D": 0, "Q": 1, "seasonal_period": 1,
            },
            _form(y[:, None]),
        )
    with pytest.raises(StepError, match="need at least"):
        _run(
            SarimaStep(),
            {
                "value_label": "y", "p": 0, "q": 1,
                "P": 0, "D": 0, "Q": 1, "seasonal_period": 4,
            },
            _form(np.arange(10, dtype=float)[:, None]),
        )
    with pytest.raises(StepError, match="zero variance"):
        _run(
            SarimaStep(),
            {
                "value_label": "y", "p": 0, "q": 1,
                "P": 0, "D": 0, "Q": 1, "seasonal_period": 4,
            },
            _form(np.ones(120, dtype=float)[:, None]),
        )
