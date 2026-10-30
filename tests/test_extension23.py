"""Hand checks for the 0.30 regression models."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.conditional_logit import ConditionalLogitStep
from src.task.step.steps.multinomial_logit import MultinomialLogitStep
from src.task.step.steps.robust_regression import RobustRegressionStep


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


def _multinomial_data():
    rng = np.random.default_rng(42)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    linear = np.column_stack([0.5 * x1 - 0.2 * x2, -0.3 * x1 + 0.7 * x2])
    prob = np.exp(linear)
    prob = np.column_stack([np.ones(n), prob])
    prob /= prob.sum(axis=1, keepdims=True)
    y = np.asarray(
        [rng.choice([1, 2, 3], p=prob[i]) for i in range(n)],
        dtype=np.float64,
    )
    return _form([y, x1, x2], ["y", "x1", "x2"])


def _conditional_data():
    rng = np.random.default_rng(7)
    groups = np.repeat(np.arange(20), 3)
    x = rng.normal(size=(60, 2))
    eta = 0.8 * x[:, 0] - 0.4 * x[:, 1]
    choice = np.zeros(60, dtype=np.float64)
    for group in range(20):
        index = np.where(groups == group)[0]
        probability = np.exp(eta[index])
        probability /= probability.sum()
        choice[rng.choice(index, p=probability)] = 1.0
    return _form(
        [choice, x[:, 0], x[:, 1], groups + 1],
        ["y", "x1", "x2", "stratum"],
    )


def _robust_data():
    rng = np.random.default_rng(8)
    n = 40
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1 + 2 * x1 - 0.5 * x2 + rng.normal(scale=0.3, size=n)
    y[0] += 20
    return _form([y, x1, x2], ["y", "x1", "x2"])


def test_multinomial_logit_matches_nnet():
    out, info = _run(
        MultinomialLogitStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _multinomial_data(),
    )
    assert out.dims == ["row", "statistic"]
    assert out.data.shape == (6, 9)
    assert info["reference"] == "1.0"
    assert info["levels"] == ["1.0", "2.0", "3.0"]
    coef = np.asarray(info["coef"])
    assert coef.shape == (3, 2)
    expected = np.asarray(
        [
            [-0.07856751, -0.03535957],
            [0.6947102, -0.3482974],
            [0.4630492, 1.1293976],
        ]
    )
    assert np.allclose(coef, expected, atol=1e-4)
    assert out.labels["row"]["x1|2.0"] == 1


def test_conditional_logit_matches_clogit():
    out, info = _run(
        ConditionalLogitStep(),
        {
            "stratum_label": "stratum",
            "event_label": "y",
            "predictors": ["x1", "x2"],
        },
        _conditional_data(),
    )
    assert out.data.shape == (2, 9)
    assert info["n_groups"] == 20
    assert info["n"] == 60
    assert info["coef"] == pytest.approx([1.0291703, -0.9972766], abs=1e-4)
    assert info["se"] == pytest.approx([0.5022442, 0.4568622], abs=1e-4)
    assert info["odds_ratio"] == pytest.approx([2.7987427, 0.3688827], abs=1e-4)


def test_robust_regression_matches_rlm():
    out, info = _run(
        RobustRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"]},
        _robust_data(),
    )
    assert out.data.shape == (3, 6)
    assert info["coef"] == pytest.approx(
        [0.9672461, 1.8805607, -0.5415845], abs=1e-4
    )
    assert info["se"] == pytest.approx(
        [0.04269196, 0.03660616, 0.04031767], abs=1e-4
    )
    assert info["scale"] == pytest.approx(0.3079868, abs=1e-4)
    assert info["df_resid"] == 37


def test_regression30_parameter_errors():
    multinomial = _multinomial_data()
    with pytest.raises(StepError, match="predictor"):
        _run(
            MultinomialLogitStep(),
            {"response_label": "y", "predictors": ["missing"]},
            multinomial,
        )
    conditional = _conditional_data()
    # Remove the event from one stratum: conditional logit must reject it.
    bad = np.array(conditional.data, copy=True)
    y_column = conditional.labels["feature"]["y"]
    stratum_column = conditional.labels["feature"]["stratum"]
    bad[bad[:, stratum_column] == bad[0, stratum_column], y_column] = 0
    bad_form = Form(
        bad,
        conditional.dims,
        conditional.labels,
        dict(conditional.info),
    )
    with pytest.raises(StepError, match="exactly one event"):
        _run(
            ConditionalLogitStep(),
            {
                "stratum_label": "stratum",
                "event_label": "y",
                "predictors": ["x1", "x2"],
            },
            bad_form,
        )
    with pytest.raises(StepError, match="predictor"):
        _run(
            RobustRegressionStep(),
            {"response_label": "y", "predictors": ["missing"]},
            _robust_data(),
        )
