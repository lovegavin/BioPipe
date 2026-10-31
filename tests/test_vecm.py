"""Hand checks for the 0.96 VECM operator."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.vecm import VecmStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(x, y):
    data = np.column_stack([np.asarray(x, dtype=float), np.asarray(y, dtype=float)])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x": 0, "y": 1},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _form_one(x):
    data = np.asarray(x, dtype=float).reshape(-1, 1)
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    rng = np.random.default_rng(20261117)
    innovations = rng.normal(size=(200, 2))
    x = np.cumsum(innovations[:, 0])
    y = 0.8 * x + innovations[:, 1]
    return x, y


def test_vecm_matches_johansen_and_statsmodels():
    x, y = _fixture()
    export, out = _run(
        VecmStep(),
        {"coint_rank": 1, "k_ar_diff": 1, "output": "fit"},
        _form(x, y),
    )
    assert out.data.shape == (8, 1)
    assert out.dims == ["term", "statistic"]
    assert set(out.labels["term"]) == {
        "trace_r0",
        "eigen_r0",
        "trace_r1",
        "eigen_r1",
        "beta_r0_x",
        "alpha_r0_x",
        "beta_r0_y",
        "alpha_r0_y",
    }
    np.testing.assert_allclose(
        export["trace_stats"], [76.26701518, 0.33506407], rtol=0, atol=1e-6
    )
    np.testing.assert_allclose(
        export["eigenvalues"], [0.31852431, 0.00169081], rtol=0, atol=1e-8
    )
    np.testing.assert_allclose(
        np.asarray(export["beta"]).ravel(),
        [1.0, -1.24881127],
        rtol=0,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        np.asarray(export["alpha"]).ravel(),
        [0.16505177, 0.83728729],
        rtol=0,
        atol=1e-6,
    )
    assert export["llf"] == pytest.approx(-558.6417862405992, abs=1e-8)
    assert export["n"] == 200


def test_vecm_rejects_invalid_specs():
    x, y = _fixture()
    form = _form(x, y)
    with pytest.raises(StepError, match="coint_rank must be"):
        _run(VecmStep(), {"coint_rank": 0}, form)
    with pytest.raises(StepError, match="coint_rank must be"):
        _run(VecmStep(), {"coint_rank": 2}, form)
    with pytest.raises(StepError, match="k_ar_diff must be"):
        _run(VecmStep(), {"k_ar_diff": 0}, form)
    with pytest.raises(StepError, match="at least 2 variables"):
        _run(VecmStep(), {}, _form_one(x))
    with pytest.raises(StepError, match="must vary"):
        _run(VecmStep(), {}, _form(np.ones(200), y))
