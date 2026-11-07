"""Outlier detection over a sequence embedding matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

_STATISTICS = ("distance", "z_score", "rank")
_STATISTIC = "statistic"


def _matrix(form, sample_dim: str, embedding_dim: str) -> np.ndarray:
    if len(form.dims) != 2 or list(form.dims) != [sample_dim, embedding_dim]:
        raise StepError(
            "esm_embedding_outlier_scan: the input must have dims [{}, {}], got {}".format(
                sample_dim, embedding_dim, list(form.dims)
            )
        )
    values = np.asarray(form.data, dtype=np.float64)
    if values.shape[0] < 3:
        raise StepError("esm_embedding_outlier_scan: at least three embeddings are required")
    if not np.all(np.isfinite(values)):
        raise StepError("esm_embedding_outlier_scan: the embedding matrix contains non-finite values")
    if values.shape[1] < 1:
        raise StepError("esm_embedding_outlier_scan: the embedding matrix has no feature columns")
    return values


def mahalanobis_distances(values: np.ndarray, ridge: float = 1e-6) -> np.ndarray:
    """Mahalanobis distance of every row to the centroid."""
    if ridge < 0.0:
        raise StepError("esm_embedding_outlier_scan: ridge must not be negative")
    centred = values - values.mean(axis=0, keepdims=True)
    covariance = np.cov(centred, rowvar=False)
    covariance = np.atleast_2d(covariance) + np.eye(values.shape[1]) * float(ridge)
    inverse = np.linalg.pinv(covariance)
    distances = np.einsum("ij,jk,ik->i", centred, inverse, centred)
    if np.any(distances < 0.0):
        raise StepError("esm_embedding_outlier_scan: a Mahalanobis distance came out negative")
    return np.sqrt(np.clip(distances, 0.0, None))


def knn_distances(values: np.ndarray, k: int) -> np.ndarray:
    """Mean Euclidean distance to the k nearest neighbours (self excluded)."""
    if k < 1:
        raise StepError("esm_embedding_outlier_scan: k must be at least 1")
    if k >= values.shape[0]:
        raise StepError(
            "esm_embedding_outlier_scan: k must be smaller than the number of embeddings ({})".format(
                values.shape[0]
            )
        )
    delta = values[:, None, :] - values[None, :, :]
    distances = np.sqrt(np.sum(delta * delta, axis=2))
    np.fill_diagonal(distances, np.inf)
    nearest = np.partition(distances, k - 1, axis=1)[:, :k]
    return nearest.mean(axis=1)


def z_scores(distances: np.ndarray) -> np.ndarray:
    """Standardise distances; a degenerate spread returns zeros."""
    spread = float(distances.std(ddof=1))
    if spread <= 0.0 or not np.isfinite(spread):
        return np.zeros_like(distances)
    return (distances - distances.mean()) / spread


def outlier_rows(distances: np.ndarray) -> list[tuple[float, float, float]]:
    """Return (distance, z-score, rank) rows; rank 1 is the most extreme."""
    z = z_scores(distances)
    order = np.argsort(-distances, kind="stable")
    ranks = np.empty(distances.shape[0], dtype=np.float64)
    ranks[order] = np.arange(1, distances.shape[0] + 1, dtype=np.float64)
    return [(float(d), float(score), float(rank)) for d, score, rank in zip(distances, z, ranks)]


class EsmEmbeddingOutlierScanStep(Step):
    """Ranks embeddings by Mahalanobis or k-nearest-neighbour distance."""

    provider = "operon-core"
    parameters_file = "esm_embedding_outlier_scan.EsmEmbeddingOutlierScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_outlier_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM Embedding Outlier Scan",
        "description": (
            "Scores every sequence embedding against the collection, using the Mahalanobis "
            "distance to the centroid or the mean distance to the k nearest neighbours, so "
            "unusual sequences surface as high scores."
        ),
        "category": "Machine Learning",
        "icon": "ChartScatter",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "sample_dim", "default": "sample"},
                        {"param": "embedding_dim", "default": "embedding"},
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (64 * 1024 * 1024, 0)

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample"))
        embedding_dim = str(params.get("embedding_dim", "embedding"))
        method = str(params.get("method", "mahalanobis"))
        if method not in ("mahalanobis", "knn"):
            raise StepError("esm_embedding_outlier_scan: method must be 'mahalanobis' or 'knn'")
        values = _matrix(inputs[0], sample_dim, embedding_dim)
        if method == "mahalanobis":
            distances = mahalanobis_distances(values, float(params.get("ridge", 1e-6)))
            detail = {"method": "mahalanobis", "ridge": float(params.get("ridge", 1e-6))}
        else:
            k = int(params.get("k", 5))
            distances = knn_distances(values, k)
            detail = {"method": "knn", "k": k}
        rows = outlier_rows(distances)
        labels = {str(label): index for index, label in enumerate(inputs[0].labels[sample_dim].keys())}
        output = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[sample_dim, _STATISTIC],
            labels={
                sample_dim: labels,
                _STATISTIC: {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                **detail,
                "n_samples": len(rows),
                "most_outlying": [
                    label
                    for label, _index in sorted(
                        labels.items(), key=lambda item: -distances[item[1]]
                    )[:5]
                ],
            },
            axis_info={},
        )
        output.validate()
        output_name = str(params.get("output", "outliers"))
        ctx[output_name] = output
        self._export_data = {
            **detail,
            "n_samples": len(rows),
            "max_distance": float(distances.max()),
            "mean_distance": float(distances.mean()),
            "most_outlying": output.info["most_outlying"],
        }
        print(
            "[esm_embedding_outlier_scan] {} embeddings, max distance {:.3f}".format(
                len(rows), float(distances.max())
            )
        )

    def export(self, ctx) -> dict:
        return dict(getattr(self, "_export_data", {}))
