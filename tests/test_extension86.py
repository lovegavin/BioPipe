"""Tests for 0.93 probit regression."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.core import Form, StepError
from src.task.step.steps.probit_regression import ProbitRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(frame: pd.DataFrame):
    data = frame.to_numpy(dtype=float)
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(frame.columns)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture() -> pd.DataFrame:
    rng = np.random.default_rng(20261116)
    n = 180
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    eta = -0.3 + 0.8 * x1 - 0.5 * x2
    p = norm.cdf(eta)
    y = rng.binomial(1, p)
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


def test_probit_matches_reference_fit():
    export = _run(
        ProbitRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "output": "fit",
        },
        _form(_fixture()),
    )
    assert export["terms"] == ["Intercept", "x1", "x2"]
    np.testing.assert_allclose(
        export["coef"],
        [-0.4671648101606798, 0.8706644589381968, -0.4035829436453195],
        atol=3e-5,
    )
    np.testing.assert_allclose(
        export["se"],
        [0.1117647031461232, 0.14877751435596978, 0.10884803202605615],
        atol=3e-5,
    )
    assert export["loglikelihood"] == pytest.approx(-92.06721188869284, abs=1e-4)
    assert export["aic"] == pytest.approx(190.13442377738568, abs=2e-4)
    assert export["n"] == 180


def test_probit_maps_numeric_two_level_response():
    frame = _fixture()
    frame["y"] = frame["y"] + 1.0
    export = _run(
        ProbitRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _form(frame),
    )
    assert export["levels"] == ["1.0", "2.0"]
    np.testing.assert_allclose(
        export["coef"],
        [-0.4671648101606798, 0.8706644589381968, -0.4035829436453195],
        atol=3e-5,
    )


def test_probit_rejects_invalid_specs():
    frame = _fixture()
    frame.loc[:2, "y"] = 2.0
    with pytest.raises(StepError, match="exactly two levels"):
        _run(
            ProbitRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"]},
            _form(frame),
        )
    with pytest.raises(StepError, match="cannot also be a predictor"):
        _run(
            ProbitRegressionStep(),
            {"response_label": "y", "predictors": ["y", "x1"]},
            _form(_fixture()),
        )
    with pytest.raises(StepError, match="predictor 'z'"):
        _run(
            ProbitRegressionStep(),
            {"response_label": "y", "predictors": ["z"]},
            _form(_fixture()),
        )
