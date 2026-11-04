"""Tests for esm_embedding_umap_projection."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_embedding_umap_projection import (
    EsmEmbeddingUmapProjectionStep,
    knn_graph,
    spectral_embedding,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(matrix: np.ndarray, labels: list[str] | None = None) -> Form:
    rows = matrix.shape[0]
    names = labels or [f"s{index + 1}" for index in range(rows)]
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["sequence", "embedding"],
        labels={
            "sequence": {name: index for index, name in enumerate(names)},
            "embedding": {f"e{index + 1}": index for index in range(matrix.shape[1])},
        },
        info={"missing_code": np.nan},
    )


def test_knn_graph_hand_adjacency() -> None:
    points = np.array([[0.0, 0.0], [1.0, 0.0], [10.0, 0.0], [11.0, 0.0]])
    graph = knn_graph(points, 1)
    assert graph.shape == (4, 4)
    assert graph[0, 1] == 1.0 and graph[1, 0] == 1.0
    assert graph[2, 3] == 1.0 and graph[3, 2] == 1.0
    assert graph[0, 2] == 0.0
    assert np.allclose(graph, graph.T)


def test_spectral_embedding_separates_clusters() -> None:
    rng = np.random.default_rng(4)
    first = rng.normal(0.0, 0.1, size=(6, 3))
    second = rng.normal(5.0, 0.1, size=(6, 3))
    matrix = np.vstack([first, second])
    embedding = spectral_embedding(matrix, k=6, components=2)
    assert embedding.shape == (12, 2)
    # The leading non-trivial eigenvector splits the two clusters by sign.
    signs = np.sign(embedding[:, 0])
    first_agreement = max((signs[:6] > 0).mean(), (signs[:6] < 0).mean())
    second_agreement = max((signs[6:] > 0).mean(), (signs[6:] < 0).mean())
    assert first_agreement >= 5 / 6
    assert second_agreement >= 5 / 6
    assert np.sign(signs[:6].mean()) != np.sign(signs[6:].mean())
    # Deterministic sign convention: the largest magnitude is positive.
    for column in range(2):
        pivot = int(np.argmax(np.abs(embedding[:, column])))
        assert embedding[pivot, column] > 0


def test_step_output_and_labels() -> None:
    rng = np.random.default_rng(7)
    matrix = np.vstack([rng.normal(0.0, 0.2, size=(4, 4)), rng.normal(4.0, 0.2, size=(4, 4))])
    labels = [f"design{index + 1}" for index in range(8)]
    step = EsmEmbeddingUmapProjectionStep()
    ctx = Ctx({"output": "proj", "n_neighbors": 2})
    step.run(ctx, [_form(matrix, labels)])
    out = ctx["proj"]
    assert list(out.dims) == ["sequence", "component"]
    assert out.data.shape == (8, 2)
    assert sorted(out.labels["sequence"]) == sorted(labels)
    assert out.info["n_components"] == 2
    assert out.info["n_neighbors"] == 2
    assert out.info["method"] == "normalised-laplacian-spectral"
    export = step.export(ctx)
    assert export["n_sequences"] == 8
    assert len(export["spread"]) == 2


def test_three_components() -> None:
    rng = np.random.default_rng(11)
    matrix = rng.normal(0.0, 1.0, size=(6, 5))
    step = EsmEmbeddingUmapProjectionStep()
    ctx = Ctx({"output": "proj", "n_components": 3, "n_neighbors": 3})
    step.run(ctx, [_form(matrix)])
    assert ctx["proj"].data.shape == (6, 3)


def test_parameter_and_input_errors() -> None:
    rng = np.random.default_rng(3)
    matrix = rng.normal(0.0, 1.0, size=(6, 4))
    step = EsmEmbeddingUmapProjectionStep()
    with pytest.raises(StepError, match="an embedding form input is required"):
        step.run(Ctx({}), [])
    with pytest.raises(StepError, match="dims"):
        step.run(Ctx({}), [Form(data=matrix, dims=["a", "b"], labels={}, info={})])
    with pytest.raises(StepError, match="non-finite"):
        broken = matrix.copy()
        broken[0, 0] = np.nan
        step.run(Ctx({}), [_form(broken)])
    with pytest.raises(StepError, match="at least four sequences"):
        step.run(Ctx({}), [_form(matrix[:3, :])])
    with pytest.raises(StepError, match="n_components"):
        step.run(Ctx({"n_components": 5}), [_form(matrix)])
    with pytest.raises(StepError, match="k must be a positive integer"):
        step.run(Ctx({"n_neighbors": 0}), [_form(matrix)])
    with pytest.raises(StepError, match="k must be at most"):
        step.run(Ctx({"n_neighbors": 50}), [_form(matrix)])
