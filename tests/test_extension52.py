"""Hand checks for 0.59 clustering validity and agreement metrics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.adjusted_mutual_info import AdjustedMutualInfoStep
from src.task.step.steps.dunn_index import DunnIndexStep
from src.task.step.steps.silhouette_samples import SilhouetteSamplesStep


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


def test_dunn_matches_r_clustercrit():
    result, out = _run(
        DunnIndexStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    assert out.data.shape == (3, 1)
    assert out.data[0, 0] == pytest.approx(30.67572330035593, rel=1e-6)
    assert out.data[1, 0] == 6
    assert out.data[2, 0] == 2
    assert result["metric"] == "euclidean"


def test_adjusted_mutual_info_matches_r_aricode():
    first = _labels([0, 0, 0, 1, 1, 1])
    second = _labels([0, 0, 1, 1, 1, 1])
    result, out = _run(
        AdjustedMutualInfoStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [first, second],
    )
    assert out.data.shape == (4, 1)
    assert out.data[0, 0] == pytest.approx(0.33746780635745904, rel=1e-6)
    assert result["average_method"] == "max"
    assert out.data[1, 0] == 6


def test_silhouette_samples_match_r_cluster():
    result, out = _run(
        SilhouetteSamplesStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    expected = [
        0.9689982614384166,
        0.9739300984276602,
        0.9739300984276602,
        0.9677329920415768,
        0.9744462659328769,
        0.9744462659328769,
    ]
    assert out.data.shape == (6, 1)
    assert [float(out.data[i, 0]) for i in range(6)] == pytest.approx(expected, rel=1e-6)
    assert result["n_clusters"] == 2


def test_cluster_validity_invalid_inputs():
    with pytest.raises(StepError, match="at least two clusters"):
        _run(
            DunnIndexStep(),
            {"target_label": "cluster"},
            [_matrix(), _labels([0, 0, 0, 0, 0, 0])],
        )
    with pytest.raises(StepError, match="at least two clusters"):
        _run(
            SilhouetteSamplesStep(),
            {"target_label": "cluster"},
            [_matrix(), _labels([0, 0, 0, 0, 0, 0])],
        )
