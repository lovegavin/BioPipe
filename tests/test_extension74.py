"""Hand checks for 0.81 inverse Gaussian, betadisper, and ZINB."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.betadisper import BetadisperStep
from src.task.step.steps.inverse_gaussian_regression import (
    InverseGaussianRegressionStep,
)
from src.task.step.steps.zero_inflated_negative_binomial import (
    ZeroInflatedNegativeBinomialStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


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


def _ig_fixture():
    rng = np.random.default_rng(20261110)
    n = 60
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.4 + 0.4 * x1 - 0.3 * x2)
    y = rng.gamma(shape=2.0, scale=mu / 2.0)
    return np.column_stack([y, x1, x2])


def _zinb_fixture():
    from scipy.special import expit

    rng = np.random.default_rng(20261111)
    n = 220
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    z1 = rng.normal(size=n)
    mu = np.exp(0.5 + 0.4 * x1 - 0.3 * x2)
    alpha = 0.8
    theta = 1.0 / alpha
    y_nb = rng.negative_binomial(theta, theta / (theta + mu))
    zero = expit(-0.8 + 0.6 * z1)
    y = np.where(rng.random(n) < zero, 0, y_nb).astype(int)
    return np.column_stack([y, x1, x2, z1])


def _distance_form(values):
    values = np.asarray(values, dtype=float)
    n = values.shape[0]
    form = Form(
        data=values,
        dims=["sample", "sample_b"],
        labels={
            "sample": {f"s{i}": i for i in range(n)},
            "sample_b": {f"s{i}": i for i in range(n)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _group_form(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    n = values.shape[0]
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(n)},
            "feature": {"group": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _betadisper_fixture():
    a = np.array([[0, 0], [0, 1], [1, 0], [1, 1], [0.5, 0.5], [0.2, 0.8]])
    b = np.array([[3, 0], [5, 1], [6, 0], [7, 1], [4.5, 1.5], [3.5, -1.0]])
    xy = np.vstack([a, b])
    d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2))
    groups = np.array([0] * 6 + [1] * 6, dtype=float)
    return d, groups


def test_inverse_gaussian_matches_reference():
    export, form = _run(
        InverseGaussianRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "output": "ig",
        },
        [_frame_form(_ig_fixture(), ["y", "x1", "x2"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (3, 7)
    assert list(form.labels["row"]) == ["Intercept", "x1", "x2"]
    np.testing.assert_allclose(
        block[:, 0],
        [0.29112628016820374, 0.31847495391789, -0.22659950198706433],
        rtol=0,
        atol=2e-5,
    )
    np.testing.assert_allclose(
        block[:, 1],
        [0.1160139475750473, 0.08959275775038143, 0.1159005421324707],
        rtol=0,
        atol=1e-5,
    )
    assert export["deviance"] == pytest.approx(47.62187822182909, abs=1e-6)
    assert export["null_deviance"] == pytest.approx(56.22929763488882, abs=1e-6)
    assert export["n"] == 60


def test_inverse_gaussian_rejects_nonpositive_response():
    data = _ig_fixture()
    data[0, 0] = 0.0
    with pytest.raises(StepError, match="strictly positive"):
        _run(
            InverseGaussianRegressionStep(),
            {"response_label": "y", "predictors": ["x1"], "output": "ig"},
            [_frame_form(data, ["y", "x1", "x2"])],
        )


def test_betadisper_matches_vegan():
    d, groups = _betadisper_fixture()
    export, form = _run(
        BetadisperStep(),
        {"group_label": "group", "output": "bd"},
        [_distance_form(d), _group_form(groups)],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (12, 2)
    np.testing.assert_allclose(
        block[:, 0],
        [
            0.7106335201775947, 0.6363961030678895, 0.7778174593051997,
            0.7106335201775945, 0.07071067811865241, 0.35355339059327406,
            1.8800856954464142, 0.6066758241067052, 1.2388390622765431,
            2.2438186696393796, 1.1334558757279551, 1.9454362549881254,
        ],
        rtol=0,
        atol=1e-12,
    )
    assert list(export["group_means"].values()) == pytest.approx(
        [0.5432907785733675, 1.5080518970308538], abs=1e-12
    )
    assert export["F"] == pytest.approx(12.27190000879564, abs=1e-10)
    assert export["p"] == pytest.approx(0.0056966678673121976, abs=1e-14)
    assert export["eigenvalues"] == pytest.approx([70.0768332020954, 5.309000131237974], abs=1e-10)


def test_betadisper_rejects_single_group():
    d, groups = _betadisper_fixture()
    groups[:] = 0
    with pytest.raises(StepError, match="at least two groups"):
        _run(
            BetadisperStep(),
            {"group_label": "group", "output": "bd"},
            [_distance_form(d), _group_form(groups)],
        )


def test_zero_inflated_negative_binomial_matches_reference():
    export, form = _run(
        ZeroInflatedNegativeBinomialStep(),
        {
            "response_label": "y",
            "count_predictors": ["x1", "x2"],
            "zero_predictors": ["z1"],
            "output": "zinb",
        },
        [_frame_form(_zinb_fixture(), ["y", "x1", "x2", "z1"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (5, 7)
    assert list(form.labels["row"]) == [
        "count:Intercept", "count:x1", "count:x2",
        "zero:Intercept", "zero:z1",
    ]
    np.testing.assert_allclose(
        block[:, 0],
        [
            0.504542522196694, 0.35446674816788964, -0.24305519652093036,
            -0.5862120388429567, 0.537950517169738,
        ],
        rtol=0,
        atol=2e-5,
    )
    assert export["alpha"] == pytest.approx(0.7224400229926667, abs=1e-12)
    assert export["theta"] == pytest.approx(1.38419795162726, abs=1e-12)
    assert export["loglike"] == pytest.approx(-312.2941749228622, abs=1e-10)
    assert export["n_zeros"] == 125


def test_zero_inflated_negative_binomial_rejects_noninteger_counts():
    data = _zinb_fixture()
    data[0, 0] = 1.5
    with pytest.raises(StepError, match="counts must be integers"):
        _run(
            ZeroInflatedNegativeBinomialStep(),
            {
                "response_label": "y",
                "count_predictors": ["x1"],
                "zero_predictors": ["z1"],
                "output": "zinb",
            },
            [_frame_form(data, ["y", "x1", "x2", "z1"])],
        )
