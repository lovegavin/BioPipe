"""Hand checks for 0.100 additive B-spline GLM."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.additive_glm import AdditiveGlmStep


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


def _binomial_fixture():
    rng = np.random.default_rng(20261120)
    x1 = rng.normal(size=120)
    x2 = rng.uniform(-1.0, 1.0, size=120)
    eta = -0.2 + 1.1 * np.sin(x1 * 1.2) - 0.7 * x2 ** 2 + 0.4 * x1
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-eta))).astype(float)
    return x1, x2, y


def _poisson_fixture():
    rng = np.random.default_rng(20261121)
    x1 = rng.normal(size=110)
    x2 = rng.uniform(-1.0, 1.0, size=110)
    eta = 0.3 + 0.5 * np.sin(x1) - 0.2 * x2 + 0.15 * x1
    y = rng.poisson(np.exp(eta)).astype(float)
    return x1, x2, y


def test_additive_glm_binomial_reference_fit():
    x1, x2, y = _binomial_fixture()
    export, out = _run(
        AdditiveGlmStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "family": "binomial",
            "df": 4,
            "output": "fit",
        },
        _form(x1, x2, y),
    )
    assert out.data.shape == (120, 7)
    assert out.dims == ["sample", "statistic"]
    assert list(out.labels["statistic"]) == [
        "y", "linear_predictor", "fitted", "residual",
        "se_mean", "ci_low", "ci_high",
    ]
    assert export["n"] == 120
    assert export["n_basis"] == 9
    assert export["family"] == "binomial"
    assert export["levels"] == [0.0, 1.0]
    assert export["deviance"] == pytest.approx(153.67927797035628, abs=1e-8)
    assert export["null_deviance"] == pytest.approx(166.05519820921918, abs=1e-8)
    assert export["pseudo_r2"] == pytest.approx(0.07452895406062521, abs=1e-10)
    assert export["aic"] == pytest.approx(171.67927797035625, abs=1e-8)
    assert export["converged"] is True
    fitted = np.asarray(export["fitted"])
    assert np.all(fitted > 0) and np.all(fitted < 1)
    assert np.all(np.asarray(export["ci_low"]) < fitted)
    assert np.all(fitted < np.asarray(export["ci_high"]))
    np.testing.assert_allclose(
        np.asarray(export["residual"]), y - fitted, atol=1e-12
    )


def test_additive_glm_poisson_reference_fit():
    x1, x2, y = _poisson_fixture()
    export, out = _run(
        AdditiveGlmStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "family": "poisson",
            "df": 4,
        },
        _form(x1, x2, y),
    )
    assert out.data.shape == (110, 7)
    assert export["n"] == 110
    assert export["n_basis"] == 9
    assert export["family"] == "poisson"
    assert export["levels"] is None
    assert export["deviance"] == pytest.approx(111.90631057242092, abs=1e-8)
    assert export["aic"] == pytest.approx(337.2593109005014, abs=1e-8)
    assert np.all(np.asarray(export["fitted"]) > 0)
    assert np.all(np.asarray(export["ci_low"]) > 0)


def test_additive_glm_drops_missing_and_keeps_labels():
    x1, x2, y = _binomial_fixture()
    x2 = x2.copy()
    x2[7] = np.nan
    export, out = _run(
        AdditiveGlmStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "family": "binomial",
            "df": 4,
        },
        _form(x1, x2, y),
    )
    assert export["n"] == 119
    assert "s7" not in out.labels["sample"]
    assert out.labels["sample"]["s8"] == 7
    assert out.data.shape == (119, 7)


def test_additive_glm_rejects_invalid_inputs():
    x1, x2, y = _binomial_fixture()
    form = _form(x1, x2, y)
    with pytest.raises(StepError, match="need between 2 and 8"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1"], "family": "binomial"},
            form,
        )
    with pytest.raises(StepError, match="predictors must be unique"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x1"], "family": "binomial"},
            form,
        )
    with pytest.raises(StepError, match="response must not"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "y"], "family": "binomial"},
            form,
        )
    with pytest.raises(StepError, match="family must be"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "gamma"},
            form,
        )
    with pytest.raises(StepError, match="exactly two levels"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "binomial"},
            _form(x1, x2, np.arange(120) % 3),
        )
    with pytest.raises(StepError, match="nonnegative"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "poisson"},
            _form(x1, x2, -y),
        )
    with pytest.raises(StepError, match="integer counts"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "poisson"},
            _form(x1, x2, y + 0.5),
        )
    with pytest.raises(StepError, match="df keys not predictors"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "binomial", "df": {"x1": 4, "z": 4}},
            form,
        )
    with pytest.raises(StepError, match="must be in 4..10"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "binomial", "df": 3},
            form,
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            AdditiveGlmStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "family": "binomial", "df": 4},
            _form(x1, x1, y),
        )
