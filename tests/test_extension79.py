"""Tests for 0.87 ARIMA and isotonic regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.arima import ArimaStep
from src.task.step.steps.isotonic import IsotonicStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(values, labels=None):
    values = np.asarray(values, dtype=float)
    if labels is None:
        labels = ("x", "y") if values.ndim == 2 and values.shape[1] == 2 else ("y",)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _arima_series() -> np.ndarray:
    rng = np.random.default_rng(20261113)
    n = 100
    values = np.zeros(n, dtype=np.float64)
    values[0] = rng.normal()
    for i in range(1, n):
        values[i] = 0.6 * values[i - 1] + rng.normal(scale=0.8)
    return values + 1.5


def test_arima_matches_reference_fit():
    y = _arima_series()
    export = _run(
        ArimaStep(),
        {"value_label": "y", "p": 1, "d": 0, "q": 0, "output": "fit"},
        _form(y[:, None]),
    )
    assert export["terms"] == ["const", "ar.L1"]
    np.testing.assert_allclose(
        export["coef"], [1.3164335083718117, 0.6399538047622942], atol=2e-5
    )
    assert export["sigma2"] == pytest.approx(0.6130840227426311, abs=2e-5)
    assert export["aic"] == pytest.approx(241.39123602488394, abs=2e-4)
    assert export["n"] == 100


def test_arima_rejects_invalid_orders_and_series():
    with pytest.raises(StepError, match="p \\+ q"):
        _run(
            ArimaStep(),
            {"value_label": "y", "p": 0, "q": 0},
            _form(np.arange(30, dtype=float)[:, None]),
        )
    with pytest.raises(StepError, match="constant trend"):
        _run(
            ArimaStep(),
            {"value_label": "y", "p": 1, "d": 1, "q": 0},
            _form(_arima_series()[:, None]),
        )
    with pytest.raises(StepError, match="need more finite"):
        _run(
            ArimaStep(),
            {"value_label": "y", "p": 1, "q": 1},
            _form(np.arange(8, dtype=float)[:, None]),
        )


X = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=float)
Y = np.array([1.0, 2.2, 1.8, 2.7, 3.1, 2.9, 4.2, 4.0], dtype=float)


def test_isotonic_increasing_matches_r_isoreg():
    export = _run(
        IsotonicStep(),
        {"x_label": "x", "y_label": "y", "increasing": True, "output": "iso"},
        _form(np.column_stack([X, Y])),
    )
    np.testing.assert_allclose(
        export["fitted"], [1.0, 2.0, 2.0, 2.7, 3.0, 3.0, 4.1, 4.1], atol=1e-12
    )
    assert export["n"] == 8
    assert len(export["thresholds_x"]) >= 2


def test_isotonic_decreasing_matches_r_isoreg():
    export = _run(
        IsotonicStep(),
        {"x_label": "x", "y_label": "y", "increasing": False, "output": "iso"},
        _form(np.column_stack([X, Y])),
    )
    np.testing.assert_allclose(export["fitted"], np.full(8, 2.7375), atol=1e-12)
    assert export["fitted"][0] >= export["fitted"][-1]


def test_isotonic_rejects_invalid_x():
    with pytest.raises(StepError, match="unique"):
        _run(
            IsotonicStep(),
            {"x_label": "x", "y_label": "y"},
            _form(np.array([[1, 1], [1, 2], [2, 3]], dtype=float)),
        )
    with pytest.raises(StepError, match="at least 3"):
        _run(
            IsotonicStep(),
            {"x_label": "x", "y_label": "y"},
            _form(np.array([[1, 1], [2, 2]], dtype=float)),
        )
