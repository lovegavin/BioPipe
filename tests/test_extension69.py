"""Hand checks for 0.76 GARCH and VAR operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.garch import GarchStep
from src.task.step.steps.var_model import VarModelStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series_form(values, name="return"):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _frame_form(values, names):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _garch_fixture():
    rng = np.random.default_rng(20261104)
    n = 300
    returns = np.zeros(n)
    variance = np.zeros(n)
    variance[0] = 0.05 / (1.0 - 0.1 - 0.85)
    for index in range(1, n):
        variance[index] = (
            0.05 + 0.1 * returns[index - 1] ** 2 + 0.85 * variance[index - 1]
        )
        returns[index] = np.sqrt(variance[index]) * rng.standard_normal()
    return returns


def _var_fixture():
    rng = np.random.default_rng(20261105)
    n = 120
    data = np.zeros((n, 2))
    for index in range(1, n):
        data[index] = [
            0.5 * data[index - 1, 0]
            + 0.1 * data[index - 1, 1]
            + rng.normal(0, 0.4),
            0.2 * data[index - 1, 0]
            + 0.4 * data[index - 1, 1]
            + rng.normal(0, 0.4),
        ]
    return data


def test_garch_matches_arch():
    export, out = _run(
        GarchStep(),
        {"value_label": "return", "output": "garch"},
        [_series_form(_garch_fixture())],
    )
    assert out.dims == ["parameter", "statistic"]
    assert out.data.shape == (4, 4)
    assert export["parameters"] == ["mu", "omega", "alpha[1]", "beta[1]"]
    expected = np.asarray(
        [
            [0.12545912769161274, 0.05590847711009896, 2.2440090336309764, 0.024831820117366347],
            [0.21557564103295726, 0.08707941235148137, 2.475621219890903, 0.01330046022683081],
            [0.04612526785494381, 0.0411844487947326, 1.1199680754460681, 0.26272736660361085],
            [0.7269061346242348, 0.08934257972680909, 8.136166840569878, 4.079894782948119e-16],
        ]
    )
    np.testing.assert_allclose(out.data, expected, rtol=1e-6, atol=1e-8)
    assert export["persistence"] == pytest.approx(0.7730314024791786, rel=1e-8)
    assert export["conditional_volatility"][0] == pytest.approx(0.98257803, abs=1e-7)
    assert export["conditional_volatility"][-1] == pytest.approx(
        0.9331685364925081, rel=1e-8
    )
    assert export["loglikelihood"] == pytest.approx(-417.4502100666318, rel=1e-8)
    assert out.info["nobs"] == 300


def test_var_matches_statsmodels_and_r():
    export, out = _run(
        VarModelStep(),
        {"lags": 1, "output": "var"},
        [_frame_form(_var_fixture(), ["y1", "y2"])],
    )
    assert out.dims == ["equation", "term"]
    assert out.data.shape == (6, 4)
    assert export["equations"] == ["y1", "y2"]
    assert export["terms"] == ["const", "L1.y1", "L1.y2"]
    expected_coef = np.asarray(
        [
            [-0.03397482, 0.39825042, 0.12134407],
            [0.06367029, 0.17068698, 0.40692885],
        ]
    )
    expected_se = np.asarray(
        [
            [0.04032984, 0.08453865, 0.08101888],
            [0.04150812, 0.08700854, 0.08338593],
        ]
    )
    expected_t = np.asarray(
        [
            [-0.84242394, 4.7108678, 1.49772595],
            [1.53392386, 1.96172671, 4.88006607],
        ]
    )
    np.testing.assert_allclose(out.data[:, 0].reshape(2, 3), expected_coef, atol=5e-8)
    np.testing.assert_allclose(out.data[:, 1].reshape(2, 3), expected_se, atol=5e-8)
    np.testing.assert_allclose(out.data[:, 2].reshape(2, 3), expected_t, atol=5e-7)
    assert export["llf"] == pytest.approx(-137.21370301647985, rel=1e-8)
    assert out.info["lags"] == 1
    assert out.info["neqs"] == 2


def test_garch_rejects_short_constant_and_bad_fit():
    with pytest.raises(StepError, match="at least 50"):
        _run(
            GarchStep(),
            {"value_label": "return"},
            [_series_form(np.arange(20.0))],
        )
    with pytest.raises(StepError, match="zero variance"):
        _run(
            GarchStep(),
            {"value_label": "return"},
            [_series_form(np.ones(80))],
        )
    with pytest.raises(StepError, match="p and q"):
        _run(
            GarchStep(),
            {"value_label": "return", "p": 0},
            [_series_form(_garch_fixture())],
        )


def test_var_rejects_one_series_and_lag_overrun():
    with pytest.raises(StepError, match="at least two series"):
        _run(
            VarModelStep(),
            {"lags": 1},
            [_series_form(np.arange(80.0))],
        )
    with pytest.raises(StepError, match="not enough complete observations"):
        _run(
            VarModelStep(),
            {"lags": 60},
            [_frame_form(_var_fixture()[:40], ["y1", "y2"])],
        )
