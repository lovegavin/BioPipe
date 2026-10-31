"""Hand checks for 0.61 ACF, PACF, and precision-recall curve."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.acf import AcfStep
from src.task.step.steps.pacf import PacfStep
from src.task.step.steps.precision_recall_curve import PrecisionRecallCurveStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"value": 0},
        },
    )


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    return _form(
        values,
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"y": 0}},
    )


def _scores(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    return _form(
        values,
        ["sample", "score"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "score": {"p": 0}},
    )


X = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4]


def test_acf_matches_r():
    result, out = _run(AcfStep(), {"value_label": "value", "lags": 5}, [_series(X)])
    assert out.data.shape == (6, 3)
    assert out.data[0, 0] == pytest.approx(1.0, rel=1e-7)
    assert out.data[1, 0] == pytest.approx(0.55503144654088044, rel=1e-6)
    assert out.data[2, 0] == pytest.approx(-0.05974842767295601, rel=1e-6)
    assert out.data[5, 0] == pytest.approx(-0.33805031446540873, rel=1e-6)
    assert result["lags"] == 5


def test_pacf_matches_r():
    result, out = _run(PacfStep(), {"value_label": "value", "lags": 5}, [_series(X)])
    assert out.data.shape == (5, 3)
    assert out.data[0, 0] == pytest.approx(0.55503144654088044, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(-0.53156095138395143, rel=1e-6)
    assert out.data[4, 0] == pytest.approx(0.0096932454921819424, rel=1e-6)
    assert result["lags"] == 5


def test_precision_recall_curve_matches_sklearn():
    result, out = _run(
        PrecisionRecallCurveStep(),
        {"target_label": "y"},
        [_labels([0, 1, 0, 1, 1, 0, 1, 1]), _scores([0.1, 0.4, 0.2, 0.8, 0.9, 0.3, 0.7, 0.6])],
    )
    assert out.data.shape == (9, 3)
    assert out.data[0, 0] == pytest.approx(0.625, rel=1e-7)
    assert out.data[0, 1] == pytest.approx(1.0, rel=1e-7)
    assert out.data[0, 2] == pytest.approx(0.1, rel=1e-7)
    assert out.data[-1, 0] == pytest.approx(1.0, rel=1e-7)
    assert out.data[-1, 1] == pytest.approx(0.0, rel=1e-7)
    assert np.isnan(out.data[-1, 2])
    assert result["average_precision"] == pytest.approx(1.0, rel=1e-7)


def test_061_invalid_inputs():
    with pytest.raises(StepError, match="lags must be less than n"):
        _run(AcfStep(), {"value_label": "value", "lags": 12}, [_series(X)])
    with pytest.raises(StepError, match="lags must be less than n"):
        _run(PacfStep(), {"value_label": "value", "lags": 12}, [_series(X)])
    with pytest.raises(StepError, match="two classes"):
        _run(
            PrecisionRecallCurveStep(),
            {"target_label": "y"},
            [_labels([0, 0, 0, 0]), _scores([0.1, 0.2, 0.3, 0.4])],
        )
