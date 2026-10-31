"""Hand checks for 0.90 Fine-Gray subdistribution regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.fine_gray import FineGrayStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    rng = np.random.default_rng(20261114)
    n = 240
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    t1 = rng.exponential(scale=1.0 / (0.22 * np.exp(0.7 * x1 - 0.35 * x2)))
    t2 = rng.exponential(scale=1.0 / (0.12 * np.exp(-0.45 * x1 + 0.5 * x2)))
    tc = rng.exponential(scale=1.0 / 0.08, size=n)
    time = np.minimum(np.minimum(t1, t2), tc)
    status = np.where(time == t1, 1, np.where(time == t2, 2, 0))
    return np.column_stack([time, status, x1, x2]), ("time", "status", "x1", "x2")


def test_fine_gray_matches_r_crr():
    values, labels = _fixture()
    export, out = _run(
        FineGrayStep(),
        {
            "time_label": "time",
            "event_label": "status",
            "covariates": ["x1", "x2"],
            "output": "fg",
        },
        _form(values, labels),
    )
    assert out.dims == ["term", "statistic"]
    assert out.data.shape == (2, 7)
    assert out.labels["term"] == {"x1": 0, "x2": 1}
    assert out.labels["statistic"] == {
        "coef": 0,
        "HR": 1,
        "se": 2,
        "z": 3,
        "P": 4,
        "CI_low": 5,
        "CI_high": 6,
    }
    assert export["n"] == 240
    assert export["n_events"] == 109
    assert export["n_competing"] == 80
    assert export["n_censored"] == 51
    assert export["variance"] == "robust"
    coef = np.array([row["coef"] for row in export["results"]])
    se = np.array([row["se"] for row in export["results"]])
    np.testing.assert_allclose(
        coef,
        [0.94661807742758197, -0.42647421928019569],
        rtol=0,
        atol=5e-5,
    )
    np.testing.assert_allclose(
        se,
        [0.10980905345327939, 0.09209448587777204],
        rtol=0,
        atol=5e-5,
    )
    assert export["loglik"] == pytest.approx(-502.88009762162136, abs=1e-5)
    assert out.info["n_events"] == 109
    assert out.info["n_competing"] == 80
    assert out.info["converged"] is True


def test_fine_gray_no_competing_events():
    values, labels = _fixture()
    values = values.copy()
    values[values[:, 1] == 2, 1] = 0.0
    export, out = _run(
        FineGrayStep(),
        {
            "time_label": "time",
            "event_label": "status",
            "covariates": ["x1"],
            "output": "fg",
        },
        _form(values, labels),
    )
    assert export["n_competing"] == 0
    assert np.all(np.isfinite(out.data))
    assert out.data[0, 1] == pytest.approx(np.exp(out.data[0, 0]))


def test_fine_gray_custom_event_codes():
    values, labels = _fixture()
    values = values.copy()
    values[values[:, 1] == 0, 1] = 9.0
    values[values[:, 1] == 1, 1] = 5.0
    values[values[:, 1] == 2, 1] = 7.0
    export, out = _run(
        FineGrayStep(),
        {
            "time_label": "time",
            "event_label": "status",
            "covariates": ["x1", "x2"],
            "event_code": 5,
            "censor_code": 9,
            "output": "fg",
        },
        _form(values, labels),
    )
    assert export["n_events"] == 109
    assert export["n_competing"] == 80
    assert export["n_censored"] == 51
    np.testing.assert_allclose(
        out.data[:, 0],
        [0.94661807742758197, -0.42647421928019569],
        rtol=0,
        atol=5e-5,
    )


def test_fine_gray_rejects_invalid_inputs():
    values, labels = _fixture()
    form = _form(values, labels)
    with pytest.raises(StepError, match="at least two target events"):
        _run(
            FineGrayStep(),
            {"time_label": "time", "event_label": "status", "covariates": ["x1"], "event_code": 9},
            form,
        )
    with pytest.raises(StepError, match="must differ"):
        _run(
            FineGrayStep(),
            {
                "time_label": "time",
                "event_label": "status",
                "covariates": ["x1"],
                "event_code": 1,
                "censor_code": 1,
            },
            form,
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            FineGrayStep(),
            {"time_label": "time", "event_label": "status", "covariates": ["x1", "x1"]},
            form,
        )
    with pytest.raises(StepError, match="not found"):
        _run(
            FineGrayStep(),
            {"time_label": "missing", "event_label": "status", "covariates": ["x1"]},
            form,
        )
