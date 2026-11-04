"""Tests for esm_embedding_pca_loadings."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_embedding_pca_loadings import (
    EsmEmbeddingPcaLoadingsStep,
    pca_loadings,
)

MATRIX = np.asarray([
    [1.0, 0.0, 1.0],
    [2.0, 1.0, 0.0],
    [3.0, 0.0, 2.0],
    [4.0, 2.0, 1.0],
], dtype=np.float64)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(matrix):
    rows, columns = matrix.shape
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"s{index}": index for index in range(rows)},
            "embedding": {f"e{index}": index for index in range(columns)},
        },
        info={"missing_code": np.nan},
        axis_info={},
    )


def test_matches_numpy_svd() -> None:
    result = pca_loadings(MATRIX, 2)
    centered = MATRIX - MATRIX.mean(axis=0)
    _, singular, vt = np.linalg.svd(centered, full_matrices=False)
    expected_loadings = vt[:2].T * np.sqrt(singular[:2] ** 2 / 3.0)
    np.testing.assert_allclose(result["loadings"], expected_loadings, rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(
        result["explained_variance_ratio"], (singular[:2] ** 2) / (singular ** 2).sum(), rtol=1e-9
    )
    np.testing.assert_allclose(result["components"] @ result["components"].T, np.eye(2), atol=1e-9)


def test_step_output() -> None:
    ctx = Ctx({"output": "out", "n_components": 2})
    step = EsmEmbeddingPcaLoadingsStep()
    step.run(ctx, [_form(MATRIX)])
    out = ctx["out"]
    assert out.data.shape == (3, 2)
    assert list(out.labels["component"]) == ["PC1", "PC2"]
    assert list(out.labels["embedding"]) == ["e0", "e1", "e2"]
    ratios = out.info["explained_variance_ratio"]
    assert ratios == sorted(ratios, reverse=True)
    assert out.info["n_embeddings"] == 4
    assert step.export(ctx)["n_components"] == 2


def test_errors() -> None:
    with pytest.raises(StepError, match="at least two embeddings"):
        pca_loadings(np.asarray([[1.0, 2.0]]), 1)
    with pytest.raises(StepError, match="no variance"):
        pca_loadings(np.ones((3, 2)), 1)
    with pytest.raises(StepError, match="n_components must be between"):
        pca_loadings(MATRIX, 5)
    with pytest.raises(StepError, match="must be two-dimensional"):
        pca_loadings(np.asarray([1.0, 2.0, 3.0]), 1)
    step = EsmEmbeddingPcaLoadingsStep()
    with pytest.raises(StepError, match="is required"):
        step.run(Ctx({"output": "out", "sequence_dim": "other"}), [_form(MATRIX)])
    bad = _form(MATRIX)
    bad.data[0, 0] = np.nan
    with pytest.raises(StepError, match="non-finite"):
        step.run(Ctx({"output": "out"}), [bad])


def test_single_feature_component() -> None:
    result = pca_loadings(MATRIX[:, :1], 1)
    assert result["loadings"].shape == (1, 1)
