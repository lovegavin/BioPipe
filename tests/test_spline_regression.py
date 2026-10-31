"""Hand checks for 0.95 B-spline regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.spline_regression import SplineRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(x, y):
    data = np.column_stack([np.asarray(x, dtype=float), np.asarray(y, dtype=float)])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x": 0, "y": 1},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


X = np.arange(1.0, 31.0)
Y = np.sin(X / 4.0) + 0.05 * X + 0.2 * np.cos(X * 1.3)


def test_spline_regression_matches_r_bs_fit():
    export, out = _run(
        SplineRegressionStep(),
        {"response_label": "y", "predictor_label": "x", "df": 5, "output": "fit"},
        _form(X, Y),
    )
    assert out.data.shape == (30, 7)
    assert out.dims == ["sample", "statistic"]
    assert export["r2"] == pytest.approx(0.9594966682092715, abs=1e-10)
    assert export["df"] == 5
    assert export["n"] == 30
    assert out.info["degree"] == 3
    assert out.info["n_basis"] == 5
    residual = Y - np.asarray(export["fitted"])
    np.testing.assert_allclose(residual, export["residual"], rtol=0, atol=1e-12)
    assert np.all(export["ci_low"] < np.asarray(export["fitted"]))
    assert np.all(np.asarray(export["fitted"]) < export["ci_high"])


def test_spline_regression_drops_missing_and_keeps_labels():
    y = Y.copy()
    y[7] = np.nan
    export, out = _run(
        SplineRegressionStep(),
        {"response_label": "y", "predictor_label": "x", "df": 4, "output": "fit"},
        _form(X, y),
    )
    assert export["n"] == 29
    assert "s7" not in out.labels["sample"]
    assert out.labels["sample"]["s8"] == 7
    assert out.data.shape == (29, 7)


def test_spline_regression_rejects_invalid_inputs():
    form = _form(X, Y)
    with pytest.raises(StepError, match="df must be"):
        _run(SplineRegressionStep(), {"response_label": "y", "predictor_label": "x", "df": 3}, form)
    with pytest.raises(StepError, match="different columns"):
        _run(SplineRegressionStep(), {"response_label": "x", "predictor_label": "x"}, form)
    with pytest.raises(StepError, match="at least df"):
        _run(
            SplineRegressionStep(),
            {"response_label": "y", "predictor_label": "x", "df": 5},
            _form(X[:5], Y[:5]),
        )
    with pytest.raises(StepError, match="predictor must vary"):
        _run(SplineRegressionStep(), {"response_label": "y", "predictor_label": "x"}, _form(np.ones(10), Y[:10]))
    with pytest.raises(StepError, match="column 'z' not found"):
        _run(SplineRegressionStep(), {"response_label": "y", "predictor_label": "z"}, form)
