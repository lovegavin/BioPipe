"""Hand checks for the interval-censored Weibull AFT operator."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.interval_censored_regression import (
    IntervalCensoredRegressionStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(lower, upper, x1, x2):
    data = np.column_stack(
        [
            np.asarray(x1, dtype=float),
            np.asarray(x2, dtype=float),
            np.asarray(lower, dtype=float),
            np.asarray(upper, dtype=float),
        ]
    )
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x1": 0, "x2": 1, "lower": 2, "upper": 3},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    n = 24
    x1 = np.linspace(-1.2, 1.2, n)
    x2 = np.cos(np.arange(n) * 0.7)
    lower = np.array([0.5 + 0.2 * i for i in range(18)] + [0.0, 0.0, 8.0, 9.0, 1.0, 3.0])
    upper = np.array([lower[i] + 0.4 for i in range(18)] + [1.0, 0.8, np.inf, np.inf, 1.5, 3.0])
    return lower, upper, x1, x2


def _params(**extra):
    params = {
        "time_lower_label": "lower",
        "time_upper_label": "upper",
        "covariates": ["x1", "x2"],
        "output": "fit",
    }
    params.update(extra)
    return params


def test_interval_censored_hand_fixture():
    lower, upper, x1, x2 = _fixture()
    export, out = _run(
        IntervalCensoredRegressionStep(),
        _params(),
        _form(lower, upper, x1, x2),
    )
    assert out.data.shape == (4, 6)
    assert out.dims == ["term", "statistic"]
    assert list(out.labels["term"]) == [
        "Intercept", "x1", "x2", "log_scale",
    ]
    assert list(out.labels["statistic"]) == [
        "coef", "se", "z", "P", "CI_low", "CI_high",
    ]
    assert export["n"] == 24
    assert export["n_exact"] == 1
    assert export["n_interval"] == 19
    assert export["n_right"] == 2
    assert export["n_left"] == 2
    assert export["scale"] > 0
    assert export["shape"] > 0
    assert np.isfinite(export["loglik"])
    assert export["converged"] is True
    values = np.asarray(out.data)
    assert np.isfinite(values).all()
    assert np.all(np.asarray(export["standard_errors"]) > 0)
    assert np.all(values[:, 4] < values[:, 0])
    assert np.all(values[:, 0] < values[:, 5])


def test_interval_censored_right_and_exact_counts():
    lower, upper, x1, x2 = _fixture()
    export, _ = _run(
        IntervalCensoredRegressionStep(),
        _params(confidence=0.9),
        _form(lower, upper, x1, x2),
    )
    assert export["n_right"] == 2
    assert export["n_exact"] == 1
    assert export["confidence"] == 0.9
    assert export["n_left"] == 2


def test_interval_censored_rejects_invalid_inputs():
    lower, upper, x1, x2 = _fixture()

    bad_upper = upper.copy()
    bad_upper[0] = lower[0] - 1.0
    with pytest.raises(StepError, match="upper times"):
        _run(
            IntervalCensoredRegressionStep(),
            _params(),
            _form(lower, bad_upper, x1, x2),
        )

    all_right = np.full(lower.shape, np.inf)
    with pytest.raises(StepError, match="at least one finite"):
        _run(
            IntervalCensoredRegressionStep(),
            _params(),
            _form(lower, all_right, x1, x2),
        )

    exact = np.linspace(1.0, 2.0, lower.size)
    with pytest.raises(StepError, match="exact-only"):
        _run(
            IntervalCensoredRegressionStep(),
            _params(),
            _form(exact, exact, x1, x2),
        )

    with pytest.raises(StepError, match="rank deficient"):
        _run(
            IntervalCensoredRegressionStep(),
            _params(),
            _form(lower, upper, x1, np.ones(lower.size)),
        )
