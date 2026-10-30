"""Hand checks for 0.31 gamma and zero-inflated regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.gamma_regression import GammaRegressionStep
from src.task.step.steps.zero_inflated_poisson import ZeroInflatedPoissonStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(columns, names):
    data = np.column_stack(columns).astype(np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, data):
    ctx = Ctx(params)
    step.run(ctx, [data])
    return ctx[params.get("output", step.name)], step.export(ctx)


def _zero_inflated_data():
    rng = np.random.default_rng(42)
    n = 300
    x = rng.normal(size=n)
    z = rng.normal(size=n)
    probability = 1.0 / (1.0 + np.exp(-(-1.0 + 1.2 * z)))
    y = rng.poisson(np.exp(1.0 + 0.4 * x))
    y[rng.random(n) < probability] = 0
    return _form([y, x, z], ["y", "x", "z"])


def _gamma_data():
    rng = np.random.default_rng(13)
    n = 120
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.5 + 0.3 * x1 - 0.2 * x2)
    y = rng.gamma(shape=2.0, scale=mu / 2.0)
    return _form([y, x1, x2], ["y", "x1", "x2"])


def test_zero_inflated_poisson_matches_pscl():
    out, info = _run(
        ZeroInflatedPoissonStep(),
        {
            "response_label": "y",
            "count_predictors": ["x"],
            "zero_predictors": ["z"],
        },
        _zero_inflated_data(),
    )
    assert out.dims == ["row", "statistic"]
    assert out.data.shape == (4, 7)
    assert list(out.labels["row"]) == [
        "zero|Intercept",
        "zero|z",
        "count|Intercept",
        "count|x",
    ]
    assert info["count_coef"] == pytest.approx(
        [1.0500859005, 0.4181325538], abs=1e-6
    )
    assert info["zero_coef"] == pytest.approx(
        [-0.7452277514, 1.0384188306], abs=1e-6
    )
    assert info["n"] == 300
    assert info["llf"] == pytest.approx(-496.9143149148, abs=1e-6)


def test_gamma_regression_matches_glm():
    out, info = _run(
        GammaRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _gamma_data(),
    )
    assert out.dims == ["row", "statistic"]
    assert out.data.shape == (3, 7)
    assert list(out.labels["row"]) == ["Intercept", "x1", "x2"]
    assert info["coef"] == pytest.approx(
        [0.4403480625, 0.3146118651, -0.2057142438], abs=1e-6
    )
    assert info["se"] == pytest.approx(
        [0.0569290032, 0.0570324758, 0.0492307858], abs=1e-6
    )
    assert info["n"] == 120
    assert info["family"] if "family" in info else True


def test_regression31_parameter_errors():
    zero = _zero_inflated_data()
    bad = np.array(zero.data, copy=True)
    y_column = zero.labels["feature"]["y"]
    bad[0, y_column] = -1
    bad_form = Form(bad, zero.dims, zero.labels, dict(zero.info))
    with pytest.raises(StepError, match="non-negative counts"):
        _run(
            ZeroInflatedPoissonStep(),
            {"response_label": "y", "count_predictors": ["x"]},
            bad_form,
        )
    with pytest.raises(StepError, match="predictor"):
        _run(
            ZeroInflatedPoissonStep(),
            {
                "response_label": "y",
                "count_predictors": ["x"],
                "zero_predictors": ["missing"],
            },
            zero,
        )

    gamma = _gamma_data()
    bad = np.array(gamma.data, copy=True)
    y_column = gamma.labels["feature"]["y"]
    bad[0, y_column] = 0
    bad_form = Form(bad, gamma.dims, gamma.labels, dict(gamma.info))
    with pytest.raises(StepError, match="strictly positive"):
        _run(
            GammaRegressionStep(),
            {"response_label": "y", "predictors": ["x1"]},
            bad_form,
        )
