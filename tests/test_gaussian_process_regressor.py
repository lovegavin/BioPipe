"""Hand checks for 0.97 Gaussian-process regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.gaussian_process_regressor import GaussianProcessRegressorStep


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


def _manual_gp(x, y, length_scale, alpha, normalize_y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if normalize_y:
        mean = y.mean()
        scale = y.std(ddof=0)
        target = (y - mean) / scale
    else:
        mean = 0.0
        scale = 1.0
        target = y
    diff = (x[:, None, :] - x[None, :, :]) / length_scale
    kernel = np.exp(-0.5 * np.sum(diff * diff, axis=2))
    system = kernel + alpha * np.eye(x.shape[0])
    chol = np.linalg.cholesky(system)
    coef = np.linalg.solve(chol.T, np.linalg.solve(chol, target))
    fitted = kernel @ coef
    solved = np.linalg.solve(chol, kernel)
    variance = 1.0 - np.sum(solved * solved, axis=0)
    return fitted * scale + mean, np.sqrt(np.maximum(variance, 0.0)) * scale


def test_gaussian_process_matches_closed_form():
    x = np.linspace(0.0, 3.0, 12)[:, None]
    y = np.sin(x[:, 0]) + 0.1 * np.cos(2.0 * x[:, 0])
    export, out = _run(
        GaussianProcessRegressorStep(),
        {
            "response_label": "y",
            "predictors": ["x"],
            "length_scale": 1.3,
            "alpha": 1e-4,
            "output": "gp",
        },
        _form(x[:, 0], y),
    )
    fitted, se = _manual_gp(x, y, np.array([1.3]), 1e-4, True)
    np.testing.assert_allclose(export["fitted"], fitted, rtol=0, atol=1e-10)
    np.testing.assert_allclose(export["se"], se, rtol=0, atol=1e-10)
    assert out.data.shape == (12, 4)
    assert out.dims == ["sample", "statistic"]
    assert out.labels["sample"]["s0"] == 0
    assert np.allclose(out.data[:, 0], y)
    assert np.allclose(out.data[:, 2], y - fitted)
    assert export["n"] == 12
    assert export["n_features"] == 1
    assert export["r2"] > 0.9


def test_gaussian_process_accepts_per_feature_scale_and_missing():
    rng = np.random.default_rng(20261118)
    x1 = rng.normal(size=20)
    x2 = rng.normal(size=20)
    y = 0.8 * x1 - 0.2 * x2 + rng.normal(scale=0.05, size=20)
    form = _form(x1, y)
    form = Form(
        data=np.column_stack([x1, x2, y]),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {"x1": 0, "x2": 1, "y": 2},
        },
        info={"missing_code": np.nan},
    )
    form.data[3, 2] = np.nan
    form.validate()
    export, out = _run(
        GaussianProcessRegressorStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "length_scale": {"x1": 0.8, "x2": 2.0},
            "alpha": 1e-3,
            "normalize_y": False,
            "output": "gp",
        },
        form,
    )
    assert export["n"] == 19
    assert "s3" not in out.labels["sample"]
    assert export["length_scale"] == [0.8, 2.0]
    assert out.data.shape == (19, 4)


def test_gaussian_process_rejects_invalid_specs():
    x = np.linspace(0, 2, 8)
    y = np.sin(x)
    form = _form(x, y)
    with pytest.raises(StepError, match="response must not"):
        _run(
            GaussianProcessRegressorStep(),
            {"response_label": "y", "predictors": ["y"]},
            form,
        )
    with pytest.raises(StepError, match="unknown length_scale"):
        _run(
            GaussianProcessRegressorStep(),
            {"response_label": "y", "predictors": ["x"], "length_scale": {"z": 1.0}},
            form,
        )
    with pytest.raises(StepError, match="alpha must be"):
        _run(
            GaussianProcessRegressorStep(),
            {"response_label": "y", "predictors": ["x"], "alpha": -1.0},
            form,
        )
    with pytest.raises(StepError, match="at least 2"):
        _run(
            GaussianProcessRegressorStep(),
            {"response_label": "y", "predictors": ["x"]},
            _form(x[:1], y[:1]),
        )
