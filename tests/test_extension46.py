"""Hand checks for the 0.53 scale, outlier, and calibration operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.ansari_bradley import AnsariBradleyStep
from src.task.step.steps.calibration_curve import CalibrationCurveStep
from src.task.step.steps.chisq_out_test import ChiSquareOutTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"value": 0}},
    )


def _grouped(values, groups):
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    n = len(groups)
    expression = _form(
        np.asarray(values, dtype=float).reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def _calibration():
    truth = np.array([0, 0, 0, 0] + [1] * 16, dtype=float)
    probability = np.array([0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
                            0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99])
    return _form(
        np.column_stack([truth, probability]),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(20)}, "feature": {"truth": 0, "prob": 1}},
    )


def test_ansari_bradley_matches_r():
    expression, meta = _grouped(
        [1, 2, 3, 4, 5, 1, 4, 9, 16, 25],
        ["A"] * 5 + ["B"] * 5,
    )
    result, out = _run(
        AnsariBradleyStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(18.0, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(1.0392304845413265, rel=1e-6)
    assert out.data[0, 2] == pytest.approx(0.29869755599497028, rel=1e-6)
    assert out.data[0, 3] == 5
    assert out.data[0, 4] == 5
    assert out.data[0, 5] == 1
    assert result["method"] == "normal approximation"


def test_chisq_out_test_matches_r():
    values = [1, 2, 3, 4, 5, 100]
    result, out = _run(ChiSquareOutTestStep(), {"value_label": "value"}, [_series(values)])
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(4.161359374447157, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(0.04135620027516618, rel=1e-6)
    assert out.data[2, 0] == 100
    assert out.data[3, 0] == 6
    assert result["direction"] == "high"

    result, out = _run(
        ChiSquareOutTestStep(),
        {"value_label": "value", "opposite": True},
        [_series(values)],
    )
    assert out.data[0, 0] == pytest.approx(0.21018646286664547, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(0.6466212955873326, rel=1e-6)
    assert out.data[2, 0] == 1
    assert result["direction"] == "low"


def test_calibration_curve_matches_sklearn():
    result, out = _run(
        CalibrationCurveStep(),
        {"true_label": "truth", "prob_label": "prob", "n_bins": 5},
        [_calibration()],
    )
    assert out.data.shape == (5, 5)
    expected = np.array(
        [
            [0.0, 0.2, 0.125, 0.0, 4.0],
            [0.2, 0.4, 0.325, 1.0, 4.0],
            [0.4, 0.6, 0.525, 1.0, 4.0],
            [0.6, 0.8, 0.725, 1.0, 4.0],
            [0.8, 1.0, 0.9225, 1.0, 4.0],
        ],
        dtype=float,
    )
    np.testing.assert_allclose(out.data, expected, rtol=1e-6, atol=1e-7)
    assert result["strategy"] == "uniform"
    assert result["n_bins"] == 5
    assert result["n_samples"] == 20


def test_invalid_inputs_rejected():
    expression, meta = _grouped([1, 2], ["A", "B"])
    with pytest.raises(StepError, match="at least two samples"):
        _run(
            AnsariBradleyStep(),
            {"group_label": "group", "group_a": "A", "group_b": "B"},
            [expression, meta],
        )
    with pytest.raises(StepError, match="at least three observations"):
        _run(ChiSquareOutTestStep(), {"value_label": "value"}, [_series([1, 2])])
    with pytest.raises(StepError, match="variance must be positive"):
        _run(ChiSquareOutTestStep(), {"value_label": "value"}, [_series([2, 2, 2])])
    with pytest.raises(StepError, match="binary"):
        bad = _calibration()
        bad.data[0, 0] = 2
        _run(
            CalibrationCurveStep(),
            {"true_label": "truth", "prob_label": "prob", "n_bins": 5},
            [bad],
        )
