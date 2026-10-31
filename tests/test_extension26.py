"""Hand checks for 0.33 Passing-Bablok and Deming regression."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.deming_regression import DemingRegressionStep
from src.task.step.steps.passing_bablok import PassingBablokStep


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


X = np.arange(1, 11, dtype=float)
Y = np.array([1.1, 2.0, 2.9, 4.2, 5.1, 5.9, 7.1, 8.0, 9.2, 10.1])


def test_passing_bablok_matches_mcr():
    out, info = _run(PassingBablokStep(), {"method_a": "x", "method_b": "y"}, _form([X, Y], ["x", "y"]))
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (3, 1)
    assert info["slope"] == pytest.approx(1.0, abs=1e-12)
    assert info["intercept"] == pytest.approx(0.1, abs=1e-12)
    assert info["n"] == 10


def test_deming_matches_mcr():
    out, info = _run(DemingRegressionStep(), {"method_a": "x", "method_b": "y"}, _form([X, Y], ["x", "y"]))
    assert out.data.shape == (3, 1)
    assert info["slope"] == pytest.approx(1.0090793076, abs=1e-8)
    assert info["intercept"] == pytest.approx(0.0100638082, abs=1e-8)
    assert info["error_ratio"] == 1.0
    assert info["n"] == 10


def test_method_parameter_errors():
    with pytest.raises(StepError, match="non-negative"):
        _run(PassingBablokStep(), {"method_a": "x", "method_b": "y"}, _form([X, -Y], ["x", "y"]))
    with pytest.raises(StepError, match="error_ratio must be positive"):
        _run(DemingRegressionStep(), {"method_a": "x", "method_b": "y", "error_ratio": 0}, _form([X, Y], ["x", "y"]))
    with pytest.raises(StepError, match="both measurement columns must vary"):
        _run(DemingRegressionStep(), {"method_a": "x", "method_b": "y"}, _form([X, np.ones_like(X)], ["x", "y"]))
