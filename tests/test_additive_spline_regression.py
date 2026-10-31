"""Hand checks for 0.98 additive B-spline regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.additive_spline_regression import (
    AdditiveSplineRegressionStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(x1, x2, y):
    data = np.column_stack([
        np.asarray(x1, dtype=float),
        np.asarray(x2, dtype=float),
        np.asarray(y, dtype=float),
    ])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x1": 0, "x2": 1, "y": 2},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    rng = np.random.default_rng(20261118)
    x1 = rng.normal(size=80)
    x2 = rng.uniform(-1.0, 2.0, size=80)
    y = (
        np.sin(1.4 * x1)
        + 0.25 * x2 ** 2
        - 0.15 * np.cos(2.0 * x2)
        + rng.normal(scale=0.05, size=80)
    )
    return x1, x2, y


def test_additive_spline_matches_r_bs_fit():
    x1, x2, y = _fixture()
    export, out = _run(
        AdditiveSplineRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "df": {"x1": 5, "x2": 4},
            "output": "fit",
        },
        _form(x1, x2, y),
    )
    assert out.data.shape == (80, 6)
    assert out.dims == ["sample", "statistic"]
    assert export["n"] == 80
    assert export["r2"] == pytest.approx(0.996115600178689, abs=1e-12)
    assert export["adj_r2"] == pytest.approx(0.995616177344520, abs=1e-12)
    assert export["terms"] == [
        {"predictor": "x1", "df": 5, "n_basis": 5},
        {"predictor": "x2", "df": 4, "n_basis": 4},
    ]
    residual = y - np.asarray(export["fitted"])
    np.testing.assert_allclose(
        residual, export["residual"], rtol=0, atol=1e-12
    )
    assert np.all(np.asarray(export["ci_low"]) < np.asarray(export["fitted"]))
    assert np.all(np.asarray(export["fitted"]) < export["ci_high"])


def test_additive_spline_drops_missing_and_keeps_labels():
    x1, x2, y = _fixture()
    x2 = x2.copy()
    x2[7] = np.nan
    export, out = _run(
        AdditiveSplineRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "df": 4},
        _form(x1, x2, y),
    )
    assert export["n"] == 79
    assert "s7" not in out.labels["sample"]
    assert out.labels["sample"]["s8"] == 7
    assert out.data.shape == (79, 6)


def test_additive_spline_rejects_invalid_inputs():
    x1, x2, y = _fixture()
    form = _form(x1, x2, y)
    with pytest.raises(StepError, match="predictors must be unique"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x1"]},
            form,
        )
    with pytest.raises(StepError, match="response must not"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "y"]},
            form,
        )
    with pytest.raises(StepError, match="df keys not predictors"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "df": {"x1": 4, "z": 4}},
            form,
        )
    with pytest.raises(StepError, match="df for 'x1' must be in 4..10"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "df": {"x1": 3, "x2": 4}},
            form,
        )
    with pytest.raises(StepError, match="must vary"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"]},
            _form(np.ones(80), x2, y),
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "df": 5},
            _form(x1, x1, y),
        )
    with pytest.raises(StepError, match="at least 8"):
        _run(
            AdditiveSplineRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"]},
            _form(x1[:7], x2[:7], y[:7]),
        )
