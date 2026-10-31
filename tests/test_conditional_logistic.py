"""Hand checks for conditional logistic regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.conditional_logistic import (
    ConditionalLogisticStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _fixture():
    rng = np.random.default_rng(20261123)
    rows = []
    for stratum in range(60):
        x1 = rng.normal(0, 1, 2)
        x2 = rng.normal(0, 1, 2)
        eta = 0.8 * x1 - 0.5 * x2
        probability = 1.0 / (1.0 + np.exp(-(eta[0] - eta[1])))
        case = 0 if rng.random() < probability else 1
        for j in range(2):
            rows.append((stratum, int(j == case), x1[j], x2[j]))
    return np.asarray(rows, dtype=np.float64)


def _form(values):
    names = ["stratum", "y", "x1", "x2"]
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


def _params(**extra):
    params = {
        "stratum_label": "stratum",
        "outcome_label": "y",
        "covariates": ["x1", "x2"],
        "output": "fit",
    }
    params.update(extra)
    return params


def test_conditional_logistic_hand_fixture():
    values = _fixture()
    export, out = _run(ConditionalLogisticStep(), _params(), _form(values))
    assert out.data.shape == (2, 7)
    assert out.dims == ["term", "statistic"]
    assert list(out.labels["term"]) == ["x1", "x2"]
    assert list(out.labels["statistic"]) == [
        "coef", "se", "z", "P", "CI_low", "CI_high", "OR",
    ]
    assert export["coef"] == pytest.approx(
        [1.15018089970815618, -0.43275841036190243], abs=1e-6
    )
    assert export["se"] == pytest.approx(
        [0.30497652529884012, 0.24687297746742404], abs=1e-6
    )
    assert export["loglikelihood"] == pytest.approx(
        -29.279853092991594, abs=1e-8
    )
    assert export["odds_ratio"] == pytest.approx(
        [3.15876427754401234, 0.64871719622779589], abs=1e-6
    )
    assert export["n"] == 120
    assert export["n_strata"] == 60
    assert export["n_cases"] == 60
    assert export["n_controls"] == 60
    assert out.info["levels"] == ["0", "1"]
    assert out.info["converged"] is True


def test_stratum_specific_shift_is_absorbed():
    values = _fixture()
    shifted = values.copy()
    shifted[:, 2] += 10.0 * shifted[:, 0]
    _, base = _run(ConditionalLogisticStep(), _params(), _form(values))
    _, moved = _run(ConditionalLogisticStep(), _params(), _form(shifted))
    assert np.asarray(moved.data[:, 0]) == pytest.approx(
        np.asarray(base.data[:, 0]), abs=1e-6
    )
    assert np.asarray(moved.data[:, 1]) == pytest.approx(
        np.asarray(base.data[:, 1]), abs=1e-6
    )


def test_conditional_logistic_invalid_inputs():
    values = _fixture()

    no_control = values.copy()
    no_control[no_control[:, 0] == 0, 1] = 1.0
    with pytest.raises(StepError, match="no control"):
        _run(ConditionalLogisticStep(), _params(), _form(no_control))

    bad_outcome = values.copy()
    bad_outcome[0, 1] = 2.0
    with pytest.raises(StepError, match="exactly two levels"):
        _run(ConditionalLogisticStep(), _params(), _form(bad_outcome))

    collinear = values.copy()
    collinear[:, 3] = collinear[:, 2] + 3.0 * collinear[:, 0]
    with pytest.raises(StepError, match="collinear within strata"):
        _run(
            ConditionalLogisticStep(),
            _params(covariates=["x1", "x2"]),
            _form(collinear),
        )

    with pytest.raises(StepError, match="not found"):
        _run(
            ConditionalLogisticStep(),
            _params(covariates=["missing"]),
            _form(values),
        )

    one_stratum = values.copy()
    one_stratum[:, 0] = 1.0
    with pytest.raises(StepError, match="at least two strata"):
        _run(ConditionalLogisticStep(), _params(), _form(one_stratum))
