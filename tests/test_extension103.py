"""Tests for the 1.18.0 OPTICS, BIRCH and HDBSCAN operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.birch import BirchStep
from src.task.step.steps.hdbscan import HdbscanStep
from src.task.step.steps.optics import OpticsStep

X = np.asarray([
    [0.0, 0.0], [0.2, 0.1], [0.1, 0.3], [0.3, 0.2],
    [5.0, 5.0], [5.2, 5.1], [5.1, 5.3], [5.3, 4.9],
    [9.0, 0.0], [9.2, 0.2], [8.8, 0.1], [9.1, 0.3],
])
EXPECTED_LABELS = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(matrix):
    data = np.asarray(matrix, dtype=np.float64)
    samples = [f"s{i}" for i in range(data.shape[0])]
    features = [f"f{i}" for i in range(data.shape[1])]
    return Form(
        data=data,
        dims=["sample", "feature"],
        labels={"sample": {name: i for i, name in enumerate(samples)},
                "feature": {name: i for i, name in enumerate(features)}},
        info={"missing_code": np.nan},
    )


def _run(step, params=None, matrix=X):
    ctx = Ctx(params or {})
    step.run(ctx, [_form(matrix)])
    return ctx["out"], step.export(ctx)


def test_optics_matches_sklearn():
    pytest.importorskip("sklearn")
    from sklearn.cluster import OPTICS

    form, export = _run(OpticsStep(), {"min_samples": 3, "xi": 0.05})
    labels = np.asarray(form.data[:, 0], dtype=np.int64).tolist()
    assert labels == EXPECTED_LABELS
    reference = OPTICS(min_samples=3, max_eps=np.inf, xi=0.05, metric="euclidean")
    reference.fit(X)
    assert labels == [int(v) for v in reference.labels_]
    assert export["ordering"] == [int(v) for v in reference.ordering_]
    assert export["n_clusters"] == 3
    assert export["n_noise"] == 0
    reachability = np.asarray(form.data[:, 1], dtype=np.float64)
    core = np.asarray(form.data[:, 2], dtype=np.float64)
    expected = np.asarray(reference.reachability_, dtype=np.float64)
    assert np.array_equal(np.isnan(reachability), np.isinf(expected))
    np.testing.assert_allclose(reachability[np.isfinite(expected)],
                               expected[np.isfinite(expected)], rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(core, reference.core_distances_, rtol=1e-5, atol=1e-6)
    assert form.labels["statistic"] == {"cluster": 0, "reachability": 1, "core_distance": 2}


def test_optics_rejects_bad_parameters():
    with pytest.raises(StepError, match="min_samples"):
        _run(OpticsStep(), {"min_samples": 1})
    with pytest.raises(StepError, match="xi"):
        _run(OpticsStep(), {"xi": 1.0})
    with pytest.raises(StepError, match="max_eps"):
        _run(OpticsStep(), {"max_eps": 0.0})


def test_birch_matches_sklearn():
    pytest.importorskip("sklearn")
    from sklearn.cluster import Birch

    form, export = _run(BirchStep())
    labels = np.asarray(form.data[:, 0], dtype=np.int64).tolist()
    assert labels == EXPECTED_LABELS
    reference = Birch(threshold=0.5, branching_factor=50, n_clusters=None).fit(X)
    assert labels == [int(v) for v in reference.labels_]
    assert export["n_clusters"] == 3
    assert export["n_subclusters"] == 3
    np.testing.assert_allclose(export["subcluster_centers"],
                               np.asarray(reference.subcluster_centers_), rtol=1e-9, atol=1e-9)
    assert export["requested_n_clusters"] is None
    assert form.dims == ["sample", "cluster"]


def test_birch_requested_cluster_count():
    pytest.importorskip("sklearn")
    form, export = _run(BirchStep(), {"n_clusters": 2})
    labels = np.asarray(form.data[:, 0], dtype=np.int64).tolist()
    assert labels == [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    assert export["n_clusters"] == 2
    assert export["requested_n_clusters"] == 2


def test_birch_rejects_bad_parameters():
    with pytest.raises(StepError, match="threshold"):
        _run(BirchStep(), {"threshold": 0.0})
    with pytest.raises(StepError, match="branching_factor"):
        _run(BirchStep(), {"branching_factor": 1})
    with pytest.raises(StepError, match="n_clusters"):
        _run(BirchStep(), {"n_clusters": 1})


def test_hdbscan_matches_sklearn():
    pytest.importorskip("sklearn")
    from sklearn.cluster import HDBSCAN

    form, export = _run(HdbscanStep(), {"min_cluster_size": 2, "min_samples": 2})
    labels = np.asarray(form.data[:, 0], dtype=np.int64).tolist()
    probabilities = np.asarray(form.data[:, 1], dtype=np.float64)
    assert labels == EXPECTED_LABELS
    reference = HDBSCAN(min_cluster_size=2, min_samples=2).fit(X)
    assert labels == [int(v) for v in reference.labels_]
    np.testing.assert_allclose(probabilities, reference.probabilities_, rtol=1e-5, atol=1e-6)
    assert export["n_clusters"] == 3
    assert export["n_noise"] == 0
    assert form.labels["statistic"] == {"cluster": 0, "probability": 1}


def test_hdbscan_probabilities_are_one_for_larger_clusters():
    pytest.importorskip("sklearn")
    form, export = _run(HdbscanStep(), {"min_cluster_size": 3, "min_samples": 2})
    probabilities = np.asarray(form.data[:, 1], dtype=np.float64)
    np.testing.assert_allclose(probabilities, np.ones_like(probabilities), rtol=0, atol=1e-6)
    assert export["n_clusters"] == 3


def test_hdbscan_rejects_bad_parameters():
    with pytest.raises(StepError, match="min_cluster_size"):
        _run(HdbscanStep(), {"min_cluster_size": 1})
    with pytest.raises(StepError, match="min_samples"):
        _run(HdbscanStep(), {"min_samples": 0})
    with pytest.raises(StepError, match="cluster_selection_epsilon"):
        _run(HdbscanStep(), {"cluster_selection_epsilon": -0.1})
    with pytest.raises(StepError, match="cluster_selection_method"):
        _run(HdbscanStep(), {"cluster_selection_method": "density"})


def test_hdbscan_marks_isolated_points_as_noise():
    pytest.importorskip("sklearn")
    from sklearn.cluster import HDBSCAN

    spread = np.asarray([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0], [30.0, 0.0], [40.0, 0.0]])
    form, export = _run(HdbscanStep(), {"min_cluster_size": 3, "min_samples": 1}, spread)
    labels = np.asarray(form.data[:, 0], dtype=np.int64).tolist()
    assert labels == [-1, -1, -1, -1, -1]
    assert export["n_clusters"] == 0
    assert export["n_noise"] == 5
    reference = HDBSCAN(min_cluster_size=3, min_samples=1).fit(spread)
    assert labels == [int(v) for v in reference.labels_]
