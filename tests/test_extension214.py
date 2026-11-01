"""Tests for the embedding k-means silhouette operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_embedding_kmeans_silhouette import (
    EsmEmbeddingKmeansSilhouetteStep,
    kmeans,
    silhouette,
)

pytest.importorskip("numpy")


def _form(matrix) -> Form:
    data = np.asarray(matrix, dtype=np.float32)
    rows = data.shape[0]
    return Form(
        data=data,
        dims=["sample", "embedding"],
        labels={
            "sample": {f"s{index + 1}": index for index in range(rows)},
            "embedding": {f"e{index + 1}": index for index in range(data.shape[1])},
        },
        info={"missing_code": np.nan},
    )


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params: dict, form: Form):
    ctx = Ctx(params)
    step = EsmEmbeddingKmeansSilhouetteStep()
    step.run(ctx, [form])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx)


def test_silhouette_hand_value() -> None:
    matrix = np.asarray([[0.0], [1.0], [10.0], [11.0]])
    labels = np.asarray([0, 0, 1, 1])
    # point 0: a=1, b=10.5 -> 0.9048; point 1: a=1, b=9.5 -> 0.8947
    assert silhouette(matrix, labels) == pytest.approx((0.9047619 + 0.8947368) / 2, rel=1e-6)


def test_kmeans_separates_three_clusters() -> None:
    matrix = np.asarray(
        [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [10.0, 10.0], [10.1, 10.0], [10.0, 10.1], [0.0, 10.0], [0.1, 10.0], [0.0, 10.1]]
    )
    labels, inertia = kmeans(matrix, 3, seed=0)
    assert len(set(int(value) for value in labels)) == 3
    assert inertia < 0.1
    score = silhouette(matrix, labels)
    assert score > 0.9


def test_step_output_and_best_k() -> None:
    matrix = np.asarray(
        [[0.0, 0.0], [0.2, 0.0], [0.0, 0.2], [8.0, 8.0], [8.2, 8.0], [8.0, 8.2]]
    )
    out, export = _run({"min_k": 2, "max_k": 3, "seed": 1}, _form(matrix))
    assert out.data.shape == (2, 2)
    assert out.labels["k"] == {"2": 0, "3": 1}
    assert out.labels["statistic"] == {"silhouette": 0, "inertia": 1}
    assert int(out.info["best_k"]) == 2
    assert 0.0 < float(out.info["best_silhouette"]) <= 1.0
    assert set(out.info["labels_by_k"]) == {"2", "3"}
    assert export["n_samples"] == 6


def test_sklearn_silhouette_oracle() -> None:
    sklearn_metrics = pytest.importorskip("sklearn.metrics")
    matrix = np.asarray([[0.0, 0.0], [0.5, 0.0], [0.0, 0.5], [9.0, 9.0], [9.5, 9.0], [9.0, 9.5]])
    labels = np.asarray([0, 0, 0, 1, 1, 1])
    assert silhouette(matrix, labels) == pytest.approx(
        float(sklearn_metrics.silhouette_score(matrix, labels)), rel=1e-9
    )


def test_parameter_and_input_errors() -> None:
    form = _form([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [9.0, 9.0]])
    for params, match in (
        ({"min_k": 1}, "min_k must be an integer of at least 2"),
        ({"min_k": 3, "max_k": 2}, "max_k must be an integer not below min_k"),
        ({"max_k": 4}, "max_k must stay below the number of rows"),
        ({"seed": -1, "max_k": 2}, "seed must be a non-negative integer"),
    ):
        with pytest.raises(StepError, match=match):
            _run(params, form)
    bad = Form(data=np.zeros((3, 2), dtype=np.float32) + np.nan, dims=["sample", "embedding"], labels={"sample": {"a": 0, "b": 1, "c": 2}, "embedding": {"x": 0, "y": 1}}, info={})
    with pytest.raises(StepError, match="non-finite"):
        _run({}, bad)
    wrong = Form(data=np.zeros((4, 2), dtype=np.float32), dims=["sample", "feature"], labels={"sample": {"a": 0, "b": 1, "c": 2, "d": 3}, "feature": {"x": 0, "y": 1}}, info={})
    with pytest.raises(StepError, match="are required"):
        _run({}, wrong)
    tiny = _form([[0.0], [1.0]])
    with pytest.raises(StepError, match="at least three rows"):
        _run({}, tiny)
