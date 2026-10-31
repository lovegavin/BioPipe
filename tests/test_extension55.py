"""Hand checks for 0.62 cluster agreement metrics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.fowlkes_mallows import FowlkesMallowsStep
from src.task.step.steps.homogeneity_completeness_v_measure import (
    HomogeneityCompletenessVMeasureStep,
)
from src.task.step.steps.pair_confusion_matrix import PairConfusionMatrixStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        values,
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


A = [0, 0, 0, 1, 1, 1, 2, 2, 2]
B = [0, 0, 0, 1, 1, 2, 2, 1, 1]


def test_fowlkes_mallows_matches_sklearn():
    result, out = _run(
        FowlkesMallowsStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [_labels(A), _labels(B)],
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(0.5270462766947299, rel=1e-6)
    assert out.data[1, 0] == 9
    assert result["n_clusters_a"] == 3
    assert result["n_clusters_b"] == 3


def test_homogeneity_completeness_v_measure_matches_sklearn():
    result, out = _run(
        HomogeneityCompletenessVMeasureStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [_labels(A), _labels(B)],
    )
    assert out.data.shape == (6, 1)
    assert out.data[0, 0] == pytest.approx(0.5793801642856953, rel=1e-6)
    assert out.data[1, 0] == pytest.approx(0.6000000000000002, rel=1e-6)
    assert out.data[2, 0] == pytest.approx(0.5895098274473051, rel=1e-6)
    assert result["beta"] == 1.0


def test_pair_confusion_matrix_counts():
    result, out = _run(
        PairConfusionMatrixStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [_labels(A), _labels(B)],
    )
    expected = np.asarray([[44, 10], [8, 10]], dtype=np.float64)
    assert out.data.shape == (2, 2)
    assert out.data == pytest.approx(expected)
    assert result["same_cluster_same_label"] == 44
    assert result["same_cluster_different_label"] == 10
    assert result["different_cluster_same_label"] == 8
    assert result["different_cluster_different_label"] == 10


def test_062_invalid_single_cluster():
    with pytest.raises(StepError, match="two clusters"):
        _run(
            FowlkesMallowsStep(),
            {"label_a": "cluster", "label_b": "cluster"},
            [_labels(A), _labels([0] * 9)],
        )
    with pytest.raises(StepError, match="two clusters"):
        _run(
            HomogeneityCompletenessVMeasureStep(),
            {"label_a": "cluster", "label_b": "cluster"},
            [_labels(A), _labels([0] * 9)],
        )
