"""Tests for 0.79 meta-regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.meta_regression import MetaRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _fixture():
    rng = np.random.default_rng(20261109)
    n = 24
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    variance = rng.uniform(0.03, 0.12, size=n)
    effect = (
        0.3
        + 0.5 * x1
        - 0.2 * x2
        + rng.normal(scale=0.8, size=n)
        + rng.normal(scale=np.sqrt(variance))
    )
    return np.column_stack([effect, variance, x1, x2])


def _form(data):
    data = np.asarray(data, dtype=float)
    form = Form(
        data=data,
        dims=["study", "feature"],
        labels={
            "study": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(["yi", "vi", "x1", "x2"])},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(method, data=None):
    step = MetaRegressionStep()
    ctx = Ctx(
        {
            "effect_label": "yi",
            "variance_label": "vi",
            "moderators": ["x1", "x2"],
            "method": method,
            "output": "meta",
        }
    )
    step.run(ctx, [_form(_fixture() if data is None else data)])
    return step.export(ctx), ctx["meta"]


def test_meta_regression_fixed_matches_metafor():
    export, form = _run("fixed")
    assert form.dims == ["term", "statistic"]
    assert list(form.labels["term"].keys()) == ["Intercept", "x1", "x2"]
    assert export["coef"] == pytest.approx(
        [0.5582954, 0.3417866, -0.2302585], abs=2e-6
    )
    assert export["se"] == pytest.approx(
        [0.06041857, 0.05883369, 0.05093128], abs=2e-7
    )
    assert export["tau2"] == 0.0
    assert export["Q"] == pytest.approx(109.27136626848096, abs=1e-8)
    assert export["I2"] == pytest.approx(80.78179058509915, abs=1e-8)
    assert form.data[0, 0] == pytest.approx(0.5582954, abs=2e-6)


def test_meta_regression_random_dl():
    export, _ = _run("random")
    assert export["coef"] == pytest.approx(
        [0.5431708, 0.3468496, -0.2191853], abs=2e-6
    )
    assert export["se"] == pytest.approx(
        [0.1404448, 0.1427122, 0.1167862], abs=2e-6
    )
    assert export["tau2"] == pytest.approx(0.34606677368814776, abs=1e-8)
    assert export["I2"] == pytest.approx(80.78179058509915, abs=1e-8)
    assert export["Q"] == pytest.approx(109.27136626848096, abs=1e-8)


def test_meta_regression_rejects_bad_inputs():
    data = _fixture()
    bad = data.copy()
    bad[0, 1] = 0.0
    with pytest.raises(StepError, match="variance"):
        _run("fixed", bad)

    constant = data.copy()
    constant[:, 2] = 1.0
    with pytest.raises(StepError, match="rank deficient"):
        _run("fixed", constant)

    with pytest.raises(StepError, match="more than"):
        _run("fixed", data[:3])


def test_meta_regression_requires_moderators():
    step = MetaRegressionStep()
    ctx = Ctx(
        {
            "effect_label": "yi",
            "variance_label": "vi",
            "moderators": [],
            "output": "meta",
        }
    )
    with pytest.raises(StepError):
        step.run(ctx, [_form(_fixture())])
