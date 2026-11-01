"""Tests for esm_embedding_neighbors."""
from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_embedding_neighbors import (
    EsmEmbeddingNeighborsStep,
    neighbor_indices,
    similarity_matrix,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(matrix: np.ndarray) -> Form:
    matrix = np.asarray(matrix, dtype=np.float32)
    rows, columns = matrix.shape
    return Form(
        data=matrix,
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"s{index + 1}": index for index in range(rows)},
            "embedding": {f"e{index}": index for index in range(columns)},
        },
        info={"missing_code": np.nan},
    )


def test_cosine_similarity_matches_sklearn() -> None:
    matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])
    similarity = similarity_matrix(matrix, "cosine")
    metrics = pytest.importorskip("sklearn.metrics.pairwise")
    assert np.allclose(similarity, metrics.cosine_similarity(matrix), atol=1e-9)
    assert np.allclose(np.diag(similarity), 1.0)


def test_euclidean_similarity_is_negative_distance() -> None:
    matrix = np.array([[0.0, 0.0], [3.0, 4.0], [1.0, 0.0]])
    similarity = similarity_matrix(matrix, "euclidean")
    assert similarity[0, 1] == pytest.approx(-5.0)
    assert similarity[0, 2] == pytest.approx(-1.0)
    assert similarity[1, 2] == pytest.approx(-np.hypot(2.0, 4.0))


def test_neighbor_indices_exclude_self() -> None:
    matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])
    indices = neighbor_indices(similarity_matrix(matrix, "cosine"), 1)
    assert indices.tolist() == [[1], [0], [3], [2]]


def test_step_cosine_output() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    ctx = Ctx({"k": 2, "metric": "cosine", "output": "neighbors"})
    step = EsmEmbeddingNeighborsStep()
    step.run(ctx, [_form(matrix)])
    out = ctx["neighbors"]
    assert out.data.shape == (3, 2)
    assert list(out.labels["neighbor"]) == ["1", "2"]
    assert out.labels["sequence"]["s1"] == 0
    assert out.info["neighbors"][0] == ["s3", "s2"]
    assert out.data[0, 0] == pytest.approx(np.sqrt(0.5), abs=1e-6)
    assert out.data[0, 1] == pytest.approx(0.0, abs=1e-6)
    exported = step.export(ctx)
    assert exported["k"] == 2
    assert exported["metric"] == "cosine"


def test_step_euclidean_output() -> None:
    matrix = np.array([[0.0, 0.0], [3.0, 4.0], [1.0, 0.0]])
    ctx = Ctx({"k": 1, "metric": "euclidean", "output": "neighbors"})
    EsmEmbeddingNeighborsStep().run(ctx, [_form(matrix)])
    out = ctx["neighbors"]
    assert out.data[0, 0] == pytest.approx(1.0)
    assert out.data[1, 0] == pytest.approx(np.hypot(2.0, 4.0))
    assert out.info["similarity"] is False


def test_parameter_errors() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]])
    with pytest.raises(StepError, match="metric must be"):
        EsmEmbeddingNeighborsStep().run(Ctx({"metric": "manhattan"}), [_form(matrix)])
    with pytest.raises(StepError, match="at most 1"):
        EsmEmbeddingNeighborsStep().run(Ctx({"k": 2}), [_form(matrix)])
    with pytest.raises(StepError, match="cosine similarity needs non-zero"):
        similarity_matrix(np.array([[0.0, 0.0], [1.0, 0.0]]), "cosine")
    with pytest.raises(StepError, match="must have dims"):
        bad = Form(
            data=np.zeros((2, 2), dtype=np.float32),
            dims=["row", "column"],
            labels={"row": {"a": 0, "b": 1}, "column": {"c": 0, "d": 1}},
            info={"missing_code": np.nan},
        )
        EsmEmbeddingNeighborsStep().run(Ctx({"k": 1}), [bad])
    with pytest.raises(StepError, match="at least two sequences"):
        EsmEmbeddingNeighborsStep().run(Ctx({"k": 1}), [_form(np.zeros((1, 4)))])
    with pytest.raises(StepError, match="k must be positive"):
        neighbor_indices(np.eye(3), 0)
