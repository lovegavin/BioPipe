"""Hand checks for 0.70 Engle-Granger and Johansen cointegration tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.engle_granger import EngleGrangerStep
from src.task.step.steps.johansen import JohansenStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(y, x):
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    data = np.column_stack([y, x])
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"y": 0, "x": 1},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _cointegrated():
    rng = np.random.default_rng(20261031)
    x = np.cumsum(rng.normal(size=160))
    y = 1.5 * x + rng.normal(scale=0.6, size=160)
    return y, x


def _independent():
    rng = np.random.default_rng(7)
    return np.cumsum(rng.normal(size=160)), np.cumsum(rng.normal(size=160))


def _run_eg(form, params=None):
    ctx = Ctx(params)
    step = EngleGrangerStep()
    step.run(ctx, [form])
    return step.export(ctx), ctx[step.name]


def _run_johansen(form, params=None):
    ctx = Ctx(params)
    step = JohansenStep()
    step.run(ctx, [form])
    return step.export(ctx), ctx[step.name]


def test_engle_granger_detects_cointegration():
    y, x = _cointegrated()
    result, out = _run_eg(_form(y, x), {"y_label": "y", "x_label": "x", "lags": 2})
    assert result["statistic"] == pytest.approx(-6.365675416103156, rel=1e-10)
    assert result["p"] == pytest.approx(2.536310715415716e-07, rel=1e-8)
    assert result["p"] < 0.05
    assert result["n"] == 160
    assert result["critical"]["5%"] == pytest.approx(-3.37482819, rel=1e-8)
    assert out.data.shape == (6, 1)
    assert out.dims == ["statistic", "value"]


def test_engle_granger_does_not_reject_independent_walks():
    y, x = _independent()
    result, _ = _run_eg(_form(y, x), {"y_label": "y", "x_label": "x", "lags": 2})
    assert result["p"] > 0.05
    assert result["statistic"] > result["critical"]["5%"]


def test_johansen_trace_and_eigenvalue_rank_selection():
    y, x = _cointegrated()
    result, out = _run_johansen(_form(y, x), {"det_order": 0, "k_ar_diff": 1})
    assert out.data.shape == (2, 9)
    assert out.dims == ["rank", "statistic"]
    trace = np.asarray(result["trace"])
    trace_crit = np.asarray(result["trace_critical"])
    max_eig = np.asarray(result["max_eig"])
    max_crit = np.asarray(result["max_eig_critical"])
    assert trace[0] > trace_crit[0, 1]
    assert trace[1] < trace[0]
    assert max_eig[0] > max_crit[0, 1]
    assert max_eig[1] < max_eig[0]
    assert result["eigenvalues"][0] > result["eigenvalues"][1]
    assert result["variables"] == ["y", "x"]


def test_cointegration_rejects_invalid_inputs():
    y, x = _cointegrated()
    with pytest.raises(StepError, match="both series must vary"):
        _run_eg(_form(y, np.ones_like(x)), {"y_label": "y", "x_label": "x"})
    with pytest.raises(StepError, match="lags must be less"):
        _run_eg(_form(y, x), {"y_label": "y", "x_label": "x", "lags": 160})
    with pytest.raises(StepError, match="at least 2 variables"):
        form = Form(
            np.asarray(y).reshape(-1, 1),
            ["sample", "feature"],
            {"sample": {f"s{i}": i for i in range(y.size)}, "feature": {"y": 0}},
            {"missing_code": np.nan},
        )
        form.validate()
        _run_johansen(form)
    with pytest.raises(StepError, match="k_ar_diff"):
        _run_johansen(_form(y, x), {"k_ar_diff": 160})
