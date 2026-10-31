"""Hand checks for 0.65 variance ratio, Youden index, and Krippendorff alpha."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.krippendorff_alpha import KrippendorffAlphaStep
from src.task.step.steps.variance_ratio import VarianceRatioStep
from src.task.step.steps.youden_index import YoudenIndexStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _series(values, dim="value", label="value", dtype=float):
    data = np.asarray(values, dtype=dtype).reshape(-1, 1)
    form = Form(
        data,
        ["sample", dim],
        {"sample": {f"s{i}": i for i in range(len(values))}, dim: {label: 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _labels(values):
    return _series(values, "label", "target", dtype=int)


def _matrix(values):
    data = np.asarray(values, dtype=np.float64)
    form = Form(
        data,
        ["subject", "rater"],
        {
            "subject": {f"s{i}": i for i in range(data.shape[0])},
            "rater": {f"r{i}": i for i in range(data.shape[1])},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_variance_ratio_matches_r_f_test():
    result, out = _run(VarianceRatioStep(), {}, [_series([1, 2, 3, 4, 5]), _series([2, 4, 6, 8, 10])])
    assert out.data.shape == (1, 8)
    assert out.data[0, 0] == pytest.approx(0.25, rel=1e-12)
    assert out.data[0, 1] == 4 and out.data[0, 2] == 4
    assert out.data[0, 3] == pytest.approx(0.20800000000000005, rel=1e-12)
    assert out.data[0, 4] == pytest.approx(0.026029384363481924, rel=1e-12)
    assert out.data[0, 5] == pytest.approx(2.4011324711807167, rel=1e-12)
    assert result["n1"] == 5 and result["n2"] == 5


def test_youden_index_matches_sklearn_roc():
    labels = [0, 1, 0, 1, 1, 0, 1, 0, 0, 1]
    scores = [0.1, 0.4, 0.35, 0.8, 0.65, 0.2, 0.7, 0.9, 0.3, 0.55]
    result, out = _run(YoudenIndexStep(), {"target_label": "target"}, [_labels(labels), _series(scores, "score", "score")])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(0.4, rel=1e-12)
    assert out.data[0, 1] == pytest.approx(1.0, rel=1e-12)
    assert out.data[0, 2] == pytest.approx(0.8, rel=1e-12)
    assert out.data[0, 3] == pytest.approx(0.8, rel=1e-12)
    assert result["n_pos"] == 5 and result["n_neg"] == 5


def test_krippendorff_alpha_nominal_and_interval():
    complete = [[1, 2, 3, 4], [1, 2, 3, 4], [2, 2, 4, 4], [1, 3, 3, 4]]
    result, out = _run(KrippendorffAlphaStep(), {"level": "nominal"}, [_matrix(complete)])
    assert out.data.shape == (1, 4)
    assert out.data[0, 0] == pytest.approx(-0.1052631578947365, rel=1e-12)
    assert result["n_categories"] == 4

    _, interval = _run(KrippendorffAlphaStep(), {"level": "interval"}, [_matrix(complete)])
    assert interval.data[0, 0] == pytest.approx(-0.20578778135048226, rel=1e-12)

    # R irr::kripp.alpha only applies the (m-1) coincidence denominator when
    # at least one rating is missing; this fixture is our authoritative check.
    missing = [[1, 2, 3, 4], [1, 2, 3, 4], [2, 2, 4, 4], [np.nan, 3, 3, 4]]
    _, nominal_missing = _run(KrippendorffAlphaStep(), {}, [_matrix(missing)])
    assert nominal_missing.data[0, 0] == pytest.approx(-0.08130081300812986, rel=1e-12)


def test_065_invalid_inputs():
    with pytest.raises(StepError, match="at least two finite"):
        _run(VarianceRatioStep(), {}, [_series([1]), _series([1, 2, 3])])
    with pytest.raises(StepError, match="two classes"):
        _run(
            YoudenIndexStep(),
            {"target_label": "target"},
            [_labels([1, 1, 1, 1]), _series([0.1, 0.2, 0.3, 0.4], "score", "score")],
        )
    with pytest.raises(StepError, match="two distinct"):
        _run(KrippendorffAlphaStep(), {}, [_matrix([[1, 1], [1, 1]])])
