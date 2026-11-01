"""Tests for esm_embedding_pca."""
from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_pca import (
    EsmEmbeddingPcaStep,
    pca_projection,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(matrix: np.ndarray, dims=("sequence", "embedding")) -> Form:
    rows, columns = matrix.shape
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=list(dims),
        labels={
            dims[0]: {f"s{index}": index for index in range(rows)},
            dims[1]: {f"e{index}": index for index in range(columns)},
        },
        info={"missing_code": np.nan},
    )


def test_pca_projection_matches_svd_and_sklearn() -> None:
    matrix = np.array(
        [[1.0, 0.0, 2.0], [0.0, 1.0, 3.0], [1.0, 1.0, 2.0], [2.0, 0.5, 1.5]]
    )
    projection = pca_projection(matrix, 2)
    assert projection["scores"].shape == (4, 2)
    assert projection["components"].shape == (2, 3)
    assert projection["explained_variance_ratio"].sum() <= 1.0
    assert projection["explained_variance_ratio"][0] >= projection["explained_variance_ratio"][1]
    centered = matrix - matrix.mean(axis=0)
    assert np.allclose(
        projection["scores"],
        centered @ projection["components"].T,
        atol=1e-5,
    )
    sklearn = pytest.importorskip("sklearn.decomposition")
    expected = sklearn.PCA(n_components=2).fit(matrix)
    assert np.allclose(
        projection["explained_variance_ratio"],
        expected.explained_variance_ratio_,
        atol=1e-6,
    )
    assert np.allclose(np.abs(projection["components"]), np.abs(expected.components_), atol=1e-6)


def test_step_output() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    ctx = Ctx({"n_components": 2, "output": "projection"})
    step = EsmEmbeddingPcaStep()
    step.run(ctx, [_form(matrix)])
    out = ctx["projection"]
    assert out.data.shape == (3, 2)
    assert list(out.labels["component"]) == ["PC1", "PC2"]
    assert out.labels["sequence"]["s0"] == 0
    assert out.info["n_components"] == 2
    assert len(out.info["components"]) == 2
    assert sum(out.info["explained_variance_ratio"]) == pytest.approx(
        out.info["explained_variance_ratio"][0] + out.info["explained_variance_ratio"][1]
    )
    exported = step.export(ctx)
    assert exported["n_sequences"] == 3
    assert exported["cumulative_explained_variance"] <= 1.0


def test_constant_embeddings_are_rejected() -> None:
    with pytest.raises(StepError, match="no variance"):
        pca_projection(np.ones((3, 4)), 2)


def test_parameter_errors() -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    with pytest.raises(StepError, match="at most 2"):
        pca_projection(matrix, 3)
    with pytest.raises(StepError, match="n_components must be positive"):
        EsmEmbeddingPcaStep().run(Ctx({"n_components": 0}), [_form(matrix)])
    with pytest.raises(StepError, match="must have dims"):
        EsmEmbeddingPcaStep().run(
            Ctx({"n_components": 2}), [_form(matrix, dims=("row", "column"))]
        )
    with pytest.raises(StepError, match="at least two sequences"):
        EsmEmbeddingPcaStep().run(Ctx({"n_components": 1}), [_form(np.zeros((1, 3)))])
    with pytest.raises(StepError, match="non-finite"):
        bad = np.array([[1.0, np.nan], [0.0, 1.0]])
        pca_projection(bad, 1)


def test_runner_contract(tmp_path) -> None:
    matrix = np.array([[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]])
    ctx = Context(tmp_path / "task", {"params": {}})
    ctx["embeddings"] = _form(matrix)
    run(
        ctx,
        [
            {
                "name": "esm_embedding_pca",
                "inputs": ["embeddings"],
                "params": {"n_components": 2, "output": "pca"},
            }
        ],
    )
    assert ctx["pca"].data.shape == (3, 2)
    assert (tmp_path / "task" / "output" / "steps" / "01_esm_embedding_pca.json").is_file()
