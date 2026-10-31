"""Hand and authoritative checks for the 0.27 diagnostics batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.adf_test import AdfTestStep
from src.task.step.steps.kpss_test import KpssTestStep
from src.task.step.steps.negative_binomial_regression import NegativeBinomialRegressionStep
from src.task.step.steps.poisson_regression import PoissonRegressionStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


AR1 = np.array([
    0.0000000000, 0.3047170798, -0.8571538584, 0.2361588808, 1.0822600449,
    -1.3016791617, -2.0831870039, -1.1220717992, -0.9894856718, -0.6104925606,
    -1.2193394639, 0.1477942965, 0.8664685133, 0.5859118056, 1.4787882903,
    1.3547823164, -0.0464230730, 0.3408969403, -0.7543444367, 0.4258436393,
    0.2055802726, -0.0615142000, -0.7178380644, 0.7918385000, 0.3205736180,
    -0.2359836514, -0.4937237413, 0.2360749408, 0.5070890288, 0.7169860289,
    0.8610126203, 2.6582551731, 1.1885380875, 0.2008801234, -0.6932446542,
    0.2000326301, 1.2489918708, 0.6354476648, -0.4588878781, -1.0998139425,
    -0.0092955777, 0.7376768246, 0.9857603631, -0.0740534895, 0.1877292294,
    0.2293233468, 0.3562826048, 1.0851983408, 0.8747145533, 1.2037422950,
    0.7898244465, 0.7630140666, 1.0890966658, -0.8036978204, -0.8018899086,
    -0.9515065994, -1.2097818079, -1.0010113360, 0.8943345097, -0.3292304099,
], dtype=np.float64)


def _series_form(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=np.float64).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(n)]), "feature": {"x": 0}},
    )


def test_adf_matches_tseries_statistic():
    out, info = _run(
        AdfTestStep(),
        {"value_label": "x", "lags": 2},
        [_series_form(AR1)],
    )
    assert out.data.shape == (9, 1)
    assert info["statistic"] == pytest.approx(-3.3953961017, abs=2e-5)
    assert info["p"] == pytest.approx(0.0520060831, abs=2e-5)
    assert info["used_lag"] == 2
    assert info["n"] == 60
    assert info["critical"]["5%"] == pytest.approx(-3.4905407341, abs=2e-5)
    assert out.labels["statistic"]["critical_5pct"] == 6


def test_kpss_matches_tseries():
    out, info = _run(
        KpssTestStep(),
        {"value_label": "x", "lags": 3},
        [_series_form(AR1)],
    )
    assert out.data.shape == (8, 1)
    assert info["statistic"] == pytest.approx(0.1696735045, abs=2e-5)
    assert info["p"] == pytest.approx(0.1, abs=1e-6)
    assert info["lags"] == 3
    assert out.data[out.labels["statistic"]["critical_5pct"], 0] == pytest.approx(0.463, abs=1e-6)


COUNT_X = np.linspace(-1, 1, 40)
COUNT_Y = np.array([
    1, 0, 2, 1, 0, 0, 0, 2, 0, 0, 1, 3, 0, 1, 1, 3, 1, 5, 6, 2,
    5, 0, 0, 3, 3, 2, 4, 0, 9, 2, 10, 14, 2, 1, 4, 3, 2, 3, 6, 7,
], dtype=np.float64)


def _count_form():
    return _form(
        np.column_stack([COUNT_X, COUNT_Y]),
        ["sample", "feature"],
        {
            "sample": _labels([f"s{i}" for i in range(len(COUNT_X))]),
            "feature": {"x": 0, "y": 1},
        },
    )


def test_poisson_regression_matches_r():
    out, info = _run(
        PoissonRegressionStep(),
        {"response_label": "y", "predictors": ["x"]},
        [_count_form()],
    )
    assert out.data.shape == (2, 9)
    assert info["terms"] == ["Intercept", "x"]
    assert np.allclose(info["coef"], [0.8213880961, 1.0349290039], atol=2e-6)
    assert np.allclose(info["se"], [0.1134498735, 0.1798594733], atol=2e-6)
    assert np.allclose(info["rate_ratio"], np.exp(info["coef"]), atol=1e-6)
    assert info["n"] == 40


def test_negative_binomial_regression_matches_r():
    out, info = _run(
        NegativeBinomialRegressionStep(),
        {"response_label": "y", "predictors": ["x"]},
        [_count_form()],
    )
    assert out.data.shape == (2, 9)
    # statsmodels and MASS::glm.nb use slightly different information
    # matrices for the standard errors; point estimates and alpha agree.
    assert np.allclose(info["coef"], [0.8028424, 1.1345920], atol=2e-5)
    assert info["alpha"] == pytest.approx(1 / 2.261968, rel=3e-4)
    assert np.allclose(info["se"], [0.1572, 0.2655], atol=2e-2)
    assert info["rate_ratio"][0] == pytest.approx(np.exp(info["coef"][0]), rel=1e-6)


def test_time_series_rejects_bad_parameters():
    with pytest.raises(Exception, match="less than n - 2"):
        _run(AdfTestStep(), {"value_label": "x", "lags": 60}, [_series_form(AR1)])
    with pytest.raises(Exception, match="less than n"):
        _run(KpssTestStep(), {"value_label": "x", "lags": 60}, [_series_form(AR1)])
