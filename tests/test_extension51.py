"""Hand checks for 0.58 clustering validation and agreement metrics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.adjusted_rand_index import AdjustedRandIndexStep
from src.task.step.steps.normalized_mutual_info import NormalizedMutualInfoStep
from src.task.step.steps.silhouette_score import SilhouetteScoreStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _matrix():
    data = [[0, 0], [0.2, 0.1], [0.1, 0.2], [5, 5], [5.2, 5.1], [5.1, 5.2]]
    return _form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(6)},
            "feature": {"f0": 0, "f1": 1},
        },
    )


def _labels(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
    )


def test_silhouette_matches_reference():
    result, out = _run(
        SilhouetteScoreStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    assert out.data.shape == (3, 1)
    assert out.data[0, 0] == pytest.approx(0.9722473303668445, rel=1e-6)
    assert out.data[1, 0] == 6
    assert out.data[2, 0] == 2
    assert result["metric"] == "euclidean"


def test_adjusted_rand_matches_reference():
    first = _labels([0, 0, 0, 1, 1, 1])
    second = _labels([0, 0, 1, 1, 1, 1])
    result, out = _run(
        AdjustedRandIndexStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [first, second],
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(0.32432432432432434, rel=1e-6)
    assert out.data[1, 0] == 6
    assert out.data[2, 0] == 2
    assert out.data[3, 0] == 2
    assert result["adjusted_rand_index"] == pytest.approx(0.32432432432432434)


def test_normalized_mutual_info_methods():
    first = _labels([0, 0, 0, 1, 1, 1])
    second = _labels([0, 0, 1, 1, 1, 1])
    expected = {
        "arithmetic": 0.47870397138568005,
        "geometric": 0.4791387674918639,
        "max": 0.45914791702724483,
        "min": 0.5,
    }
    for method, value in expected.items():
        result, out = _run(
            NormalizedMutualInfoStep(),
            {"label_a": "cluster", "label_b": "cluster", "average_method": method},
            [first, second],
        )
        assert out.data.shape == (4, 1)
        assert out.data[0, 0] == pytest.approx(value, rel=1e-6)
        assert result["average_method"] == method


def test_cluster_metric_invalid_inputs():
    with pytest.raises(StepError, match="at least two clusters"):
        _run(
            SilhouetteScoreStep(),
            {"target_label": "cluster"},
            [_matrix(), _labels([0, 0, 0, 0, 0, 0])],
        )
    with pytest.raises(StepError, match="must not be missing"):
        _run(
            AdjustedRandIndexStep(),
            {"label_a": "cluster", "label_b": "cluster"},
            [_labels([0, 0, 0, np.nan, 1, 1]), _labels([0, 0, 1, 1, 1, 1])],
        )
