"""Hand checks for the 0.46 robust/multivariate operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.box_m import BoxMStep
from src.task.step.steps.mahalanobis_distance import MahalanobisDistanceStep
from src.task.step.steps.sen_slope import SenSlopeStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float32),
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


def _xy():
    x = np.arange(1.0, 11.0)
    y = np.array([2.1, 4.9, 6.2, 7.8, 10.1, 12.2, 13.8, 16.1, 18.2, 19.9])
    return _form(
        np.column_stack([x, y]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(10)},
            "feature": {"x": 0, "y": 1},
        },
    )


def _mahal():
    x = np.array([
        [2, 3, 1], [3, 1, 3], [4, 6, 2], [5, 2, 5],
        [6, 8, 4], [7, 4, 7], [8, 10, 6], [9, 5, 9],
    ], dtype=float)
    return _form(
        x,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(8)},
            "feature": {"x1": 0, "x2": 1, "x3": 2},
        },
    )


def _box():
    a = np.array([[1, 2], [2, 1], [3, 3], [2, 4], [4, 2], [3, 5], [5, 3], [4, 4]], dtype=float)
    b = np.array([[5, 7], [6, 5], [7, 8], [6, 9], [8, 6], [7, 7], [9, 8], [8, 9]], dtype=float)
    c = np.array([[10, 1], [11, 3], [12, 2], [10, 4], [13, 3], [11, 5], [12, 4], [14, 2]], dtype=float)
    values = np.vstack([a, b, c])
    groups = ["A"] * 8 + ["B"] * 8 + ["C"] * 8
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    return _form(
        np.column_stack([values, codes]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(24)},
            "feature": {"v1": 0, "v2": 1, "group": 2},
        },
        {"feature": {"group": encoder}},
    )


def test_sen_slope_matches_scipy():
    result, out = _run(SenSlopeStep(), {"x_label": "x", "y_label": "y"}, [_xy()])
    assert result["slope"] == pytest.approx(1.98, rel=1e-6)
    assert result["intercept"] == pytest.approx(0.26, abs=1e-6)
    assert result["ci_low"] == pytest.approx(1.9, rel=1e-6)
    assert result["ci_high"] == pytest.approx(2.025, rel=1e-6)
    assert result["n"] == 10
    assert out.data.shape == (6, 1)


def test_mahalanobis_matches_r():
    result, out = _run(MahalanobisDistanceStep(), {}, [_mahal()])
    expected = [
        3.0759981851181237, 2.040607985480989, 4.244782214156089, 1.5578493647912683,
        1.3736388384754896, 1.481624319419268, 4.041515426497227, 3.1839836660619767,
    ]
    assert out.data.shape == (8, 2)
    assert np.allclose(out.data[:, 0], expected, rtol=1e-6, atol=1e-7)
    assert result["n_samples"] == 8
    assert result["n_features"] == 3
    assert result["max_distance"] == pytest.approx(4.244782214156089, rel=1e-6)


def test_box_m_matches_biotools():
    result, out = _run(BoxMStep(), {"group_label": "group"}, [_box()])
    assert result["M"] == pytest.approx(0.8753278628690389, rel=1e-6)
    assert result["chi2"] == pytest.approx(0.7549123896701234, rel=1e-6)
    assert result["df"] == 6
    assert result["p"] == pytest.approx(0.9932284578587726, rel=1e-6)
    assert result["n_groups"] == 3
    assert result["n_features"] == 2
    assert result["n"] == 24
    assert out.data.shape == (7, 1)


def test_046_rejects_invalid_inputs():
    constant = _form(
        np.column_stack([np.ones(3), [1, 2, 3]]),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(3)}, "feature": {"x": 0, "y": 1}},
    )
    with pytest.raises(StepError, match="constant"):
        _run(SenSlopeStep(), {"x_label": "x", "y_label": "y"}, [constant])
    small = _form(
        np.array([[2, 3, 1], [3, 1, 3], [4, 6, 2]], dtype=float),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(3)}, "feature": {"x1": 0, "x2": 1, "x3": 2}},
    )
    with pytest.raises(StepError, match="more samples"):
        _run(MahalanobisDistanceStep(), {}, [small])
    with pytest.raises(StepError, match="group"):
        _run(BoxMStep(), {"group_label": "missing"}, [_box()])
