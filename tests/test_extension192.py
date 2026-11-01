from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.esm_embedding_outlier_scan import (
    EsmEmbeddingOutlierScanStep,
    knn_distances,
    mahalanobis_distances,
    outlier_rows,
    z_scores,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(values) -> Form:
    matrix = np.asarray(values, dtype=np.float32)
    labels = {"sample": {f"s{i}": i for i in range(matrix.shape[0])}}
    return Form(
        data=matrix,
        dims=["sample", "embedding"],
        labels=labels,
        info={"missing_code": np.nan},
        axis_info={},
    )


def test_mahalanobis_matches_manual_covariance() -> None:
    values = np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [10.0, 10.0]])
    distances = mahalanobis_distances(values, 1e-9)
    centred = values - values.mean(axis=0)
    inverse = np.linalg.inv(np.cov(centred, rowvar=False) + np.eye(2) * 1e-9)
    manual = np.sqrt(np.einsum("ij,jk,ik->i", centred, inverse, centred))
    assert np.allclose(distances, manual, rtol=1e-9)
    assert distances[3] == max(distances)


def test_knn_distances_hand_values() -> None:
    values = np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]])
    assert knn_distances(values, 1) == pytest.approx([1.0, 1.0, 2.0])
    assert knn_distances(values, 2) == pytest.approx([1.5, 1.618033988749895, 2.118033988749895])


def test_z_scores_and_ranks() -> None:
    distances = np.asarray([1.0, 2.0, 3.0])
    assert z_scores(distances) == pytest.approx([-1.0, 0.0, 1.0])
    rows = outlier_rows(distances)
    assert [row[2] for row in rows] == [3.0, 2.0, 1.0]
    assert rows[2][0] == pytest.approx(3.0)
    assert z_scores(np.asarray([2.0, 2.0, 2.0])).tolist() == [0.0, 0.0, 0.0]


def test_step_output_mahalanobis_and_knn() -> None:
    form = _form([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [10.0, 10.0]])
    step = EsmEmbeddingOutlierScanStep()
    ctx = Ctx({"sample_dim": "sample", "embedding_dim": "embedding"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert list(out.dims) == ["sample", "statistic"]
    assert list(out.labels["sample"].keys()) == ["s0", "s1", "s2", "s3"]
    assert out.data[3, 2] == pytest.approx(1.0)  # rank 1 for the outlier
    assert step.export(ctx)["most_outlying"][0] == "s3"

    ctx = Ctx({"sample_dim": "sample", "embedding_dim": "embedding", "method": "knn", "k": 2})
    step = EsmEmbeddingOutlierScanStep()
    step.run(ctx, [form])
    assert ctx["out"].info["method"] == "knn"
    assert ctx["out"].data[3, 2] == pytest.approx(1.0)


def test_errors() -> None:
    step = EsmEmbeddingOutlierScanStep()
    with pytest.raises(StepError, match="at least three embeddings"):
        step.run(Ctx({"sample_dim": "sample", "embedding_dim": "embedding"}), [_form([[0.0, 0.0], [1.0, 1.0]])])
    with pytest.raises(StepError, match="must have dims"):
        step.run(Ctx({"sample_dim": "sample", "embedding_dim": "other"}), [_form(np.zeros((4, 2)))])
    with pytest.raises(StepError, match="non-finite"):
        step.run(
            Ctx({"sample_dim": "sample", "embedding_dim": "embedding"}),
            [_form(np.asarray([[0.0, 0.0], [1.0, 1.0], [np.nan, 1.0], [2.0, 2.0]]))],
        )
    with pytest.raises(StepError, match="method must be"):
        step.run(Ctx({"sample_dim": "sample", "embedding_dim": "embedding", "method": "cosine"}), [_form(np.zeros((4, 2)))])
    with pytest.raises(StepError, match="k must be smaller"):
        step.run(
            Ctx({"sample_dim": "sample", "embedding_dim": "embedding", "method": "knn", "k": 4}),
            [_form([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [2.0, 2.0]])],
        )
