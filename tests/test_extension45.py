"""Hand checks for the 0.52 normality, goodness-of-fit, and outlier tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.agostino_skewness import AgostinoSkewnessStep
from src.task.step.steps.chi_square_gof import ChiSquareGofStep
from src.task.step.steps.cochran_c_test import CochranCTestStep


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


def _counts(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["category", "feature"],
        {"category": {f"c{i}": i for i in range(n)}, "feature": {"count": 0}},
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


def test_agostino_skewness_matches_r():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]
    result, out = _run(AgostinoSkewnessStep(), {"value_label": "value"}, [_series(values)])
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(1.6060526914810145, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(2.6471420773508192, rel=1e-6)
    assert out.data[2, 0] == pytest.approx(0.0081175240201695822, rel=1e-6)
    assert out.data[3, 0] == 10
    assert result["alternative"] == "two-sided"


def test_chi_square_gof_matches_r():
    result, out = _run(ChiSquareGofStep(), {"count_label": "count"}, [_counts([10, 20, 30, 40])])
    assert out.data.shape == (5, 1)
    assert out.data[0, 0] == pytest.approx(20.0, rel=1e-6)
    assert out.data[1, 0] == 3
    assert out.data[2, 0] == pytest.approx(0.00016974243555282649, rel=1e-6)
    assert out.data[3, 0] == 4
    assert out.data[4, 0] == 100
    assert result["expected_rescaled"] is False


def test_cochran_c_matches_r():
    values = [1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 10, 20, 30, 40, 50]
    groups = ["A"] * 5 + ["B"] * 5 + ["C"] * 5
    expression, meta = _grouped(values, groups)
    result, out = _run(
        CochranCTestStep(),
        {"group_label": "group", "value_label": "value"},
        [expression, meta],
    )
    assert out.data.shape == (6, 1)
    assert out.data[0, 0] == pytest.approx(0.95238095238095233, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(7.4190133887430676e-05, rel=1e-6)
    assert out.data[2, 0] == 3
    assert out.data[3, 0] == 5
    assert out.data[4, 0] == 8
    assert out.data[5, 0] == 4
    assert result["outlier_group"] == "C"


def test_invalid_inputs_rejected():
    with pytest.raises(StepError, match="at least two categories"):
        _run(ChiSquareGofStep(), {"count_label": "count"}, [_counts([10])])
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    groups = ["A"] * 5 + ["B"] * 6
    expression, meta = _grouped(values, groups)
    with pytest.raises(StepError, match="equal group sizes"):
        _run(
            CochranCTestStep(),
            {"group_label": "group", "value_label": "value"},
            [expression, meta],
        )
