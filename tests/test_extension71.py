"""Hand checks for 0.78 beta regression and redundancy analysis."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.beta_regression import BetaRegressionStep
from src.task.step.steps.redundancy_analysis import RedundancyAnalysisStep


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


def _beta_fixture():
    rng = np.random.default_rng(20261106)
    n = 80
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    eta = 0.5 + 0.8 * x1 - 0.5 * x2
    mu = 1.0 / (1.0 + np.exp(-eta))
    phi = 8.0
    y = rng.beta(mu * phi, (1.0 - mu) * phi)
    return np.column_stack([y, x1, x2])


def _rda_fixture():
    rng = np.random.default_rng(20261107)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = np.column_stack(
        [
            1.2 * x1 - 0.7 * x2 + rng.normal(scale=0.8, size=n),
            -0.8 * x1 + 0.9 * x2 + rng.normal(scale=0.7, size=n),
            0.4 * x1 + rng.normal(scale=1.0, size=n),
            rng.normal(size=n),
        ]
    )
    return y, np.column_stack([x1, x2])


def test_beta_regression_matches_r():
    data = _beta_fixture()
    export, form = _run(
        BetaRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "output": "beta",
        },
        [_frame_form(data, ["y", "x1", "x2"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (4, 6)
    assert form.labels["row"] == {
        "Intercept": 0,
        "x1": 1,
        "x2": 2,
        "phi": 3,
    }
    np.testing.assert_allclose(
        block[:, 0],
        [0.45218830829562068, 0.74962773840681951, -0.52970059447541096, 8.44338203849741475],
        rtol=0,
        atol=2e-5,
    )
    np.testing.assert_allclose(
        block[:, 1],
        [0.079304360738738172, 0.081498782085493882, 0.082805985258789488, 1.2829694348069349],
        rtol=0,
        atol=1e-6,
    )
    assert export["n"] == 80
    assert export["llf"] == pytest.approx(44.157923586039978, abs=1e-8)


def test_beta_regression_confidence_interval():
    data = _beta_fixture()
    _, form = _run(
        BetaRegressionStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "confidence": 0.90,
            "output": "beta",
        },
        [_frame_form(data, ["y", "x1", "x2"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert np.all(block[:, 4] < block[:, 0])
    assert np.all(block[:, 0] < block[:, 5])
    width_90 = block[1, 5] - block[1, 4]
    _, form95 = _run(
        BetaRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "beta"},
        [_frame_form(data, ["y", "x1", "x2"])],
    )
    block95 = np.asarray(form95.data, dtype=float)
    assert width_90 < block95[1, 5] - block95[1, 4]


def test_beta_regression_rejects_invalid_inputs():
    data = _beta_fixture()
    response = data[:, 0].copy()
    response[0] = 0.0
    response[1] = 1.0
    with pytest.raises(StepError, match="strictly between 0 and 1"):
        _run(
            BetaRegressionStep(),
            {"response_label": "y", "predictors": ["x1"], "output": "beta"},
            [_frame_form(np.column_stack([response, data[:, 1]]), ["y", "x1"])],
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            BetaRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "output": "beta"},
            [_frame_form(np.column_stack([data[:, 0], data[:, 1], data[:, 1]]), ["y", "x1", "x2"])],
        )
    with pytest.raises(StepError, match="not enough observations"):
        _run(
            BetaRegressionStep(),
            {"response_label": "y", "predictors": ["x1", "x2"], "output": "beta"},
            [_frame_form(data[:5], ["y", "x1", "x2"])],
        )


def test_redundancy_analysis_matches_vegan():
    y, x = _rda_fixture()
    export, form = _run(
        RedundancyAnalysisStep(),
        {
            "response_dim": "feature",
            "predictor_dim": "feature",
            "n_components": 2,
            "output": "rda",
        },
        [_frame_form(y, ["y1", "y2", "y3", "y4"]), _frame_form(x, ["x1", "x2"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (2, 3)
    np.testing.assert_allclose(
        block[:, 0],
        [2.38249053751312445, 0.18382629447832174],
        rtol=0,
        atol=1e-10,
    )
    assert export["total_inertia"] == pytest.approx(5.5116445710705815, abs=1e-12)
    assert export["constrained_inertia"] == pytest.approx(2.566316831991446, abs=1e-12)
    assert export["unconstrained_inertia"] == pytest.approx(2.945327739079135, abs=1e-12)
    assert len(export["site_scores"]) == 40
    assert len(export["response_scores"]) == 4
    assert len(export["predictor_scores"]) == 2


def test_redundancy_analysis_one_component_and_errors():
    y, x = _rda_fixture()
    _, form = _run(
        RedundancyAnalysisStep(),
        {"response_dim": "feature", "predictor_dim": "feature", "n_components": 1, "output": "rda"},
        [_frame_form(y, ["y1", "y2", "y3", "y4"]), _frame_form(x, ["x1", "x2"])],
    )
    block = np.asarray(form.data, dtype=float)
    assert block.shape == (1, 3)
    assert block[0, 1] == pytest.approx(block[0, 2], abs=1e-15)
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            RedundancyAnalysisStep(),
            {"response_dim": "feature", "predictor_dim": "feature", "output": "rda"},
            [
                _frame_form(y, ["y1", "y2", "y3", "y4"]),
                _frame_form(np.column_stack([x[:, 0], x[:, 0]]), ["x1", "x2"]),
            ],
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            RedundancyAnalysisStep(),
            {"response_dim": "feature", "predictor_dim": "feature", "output": "rda"},
            [
                _frame_form(np.zeros((40, 2)), ["y1", "y2"]),
                _frame_form(x, ["x1", "x2"]),
            ],
        )
