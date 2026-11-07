"""K-means over an embedding matrix with silhouette diagnostics for each k."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def kmeans(matrix: np.ndarray, k: int, *, seed: int = 0, iterations: int = 100) -> tuple[np.ndarray, float]:
    rows = matrix.shape[0]
    rng = np.random.default_rng(seed)
    centres = [matrix[int(rng.integers(rows))]]
    while len(centres) < k:
        block = np.asarray(centres, dtype=np.float64)
        distances = np.min(np.linalg.norm(matrix[:, None, :] - block[None, :, :], axis=2), axis=1)
        total = float(distances.sum())
        if total <= 0.0:
            centres.append(matrix[int(rng.integers(rows))])
            continue
        centres.append(matrix[int(rng.choice(rows, p=distances / total))])
    centres_array = np.asarray(centres, dtype=np.float64)
    labels = np.zeros(rows, dtype=np.int64)
    for _ in range(iterations):
        distances = np.linalg.norm(matrix[:, None, :] - centres_array[None, :, :], axis=2)
        updated = np.argmin(distances, axis=1)
        if np.array_equal(updated, labels):
            break
        labels = updated
        for index in range(k):
            members = matrix[labels == index]
            if len(members) > 0:
                centres_array[index] = members.mean(axis=0)
    distances = np.linalg.norm(matrix[:, None, :] - centres_array[None, :, :], axis=2)
    inertia = float(np.sum(np.min(distances, axis=1) ** 2))
    return labels, inertia


def silhouette(matrix: np.ndarray, labels: np.ndarray) -> float:
    rows = matrix.shape[0]
    unique = np.unique(labels)
    if len(unique) < 2 or len(unique) >= rows:
        return 0.0
    distances = np.linalg.norm(matrix[:, None, :] - matrix[None, :, :], axis=2)
    scores: list[float] = []
    for index in range(rows):
        own = labels == labels[index]
        own_count = int(own.sum())
        others = [other for other in unique if other != labels[index]]
        if own_count <= 1 or not others:
            scores.append(0.0)
            continue
        a = float(distances[index][own].sum() / (own_count - 1))
        b = min(float(distances[index][labels == other].mean()) for other in others)
        denominator = max(a, b)
        scores.append(0.0 if denominator == 0.0 else (b - a) / denominator)
    return float(np.mean(scores))


class EsmEmbeddingKmeansSilhouetteStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_kmeans_silhouette.EsmEmbeddingKmeansSilhouetteStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "esm_embedding_kmeans_silhouette",
        "kind": "operator",
        "title": "Embedding k-means silhouette",
        "description": "Run deterministic k-means for a range of cluster counts over an embedding matrix and report inertia and silhouette scores.",
        "category": "Machine Learning",
        "icon": "CirclesThree",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sample_dim", "default": "sample"},
                        {"param": "embedding_dim", "default": "embedding"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("esm_embedding_kmeans_silhouette: an embedding form input is required")
        form = inputs[0]
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample") or "sample")
        embedding_dim = str(params.get("embedding_dim", "embedding") or "embedding")
        cluster_dim = str(params.get("cluster_dim", "k") or "k")
        out_name = str(params.get("output", "silhouette") or "silhouette")
        min_k = params.get("min_k")
        min_k = 2 if min_k is None else min_k
        max_k = params.get("max_k")
        max_k = 6 if max_k is None else max_k
        seed = params.get("seed")
        seed = 0 if seed is None else seed
        if list(form.dims) != [sample_dim, embedding_dim]:
            raise StepError(
                f"esm_embedding_kmeans_silhouette: dims [{sample_dim}, {embedding_dim}] are required, "
                f"got {list(form.dims)}"
            )
        matrix = np.asarray(form.data, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[0] < 3 or matrix.shape[1] < 1:
            raise StepError("esm_embedding_kmeans_silhouette: at least three rows and one column are required")
        if not np.all(np.isfinite(matrix)):
            raise StepError("esm_embedding_kmeans_silhouette: the embedding matrix contains non-finite values")
        if isinstance(min_k, bool) or not isinstance(min_k, int) or min_k < 2:
            raise StepError("esm_embedding_kmeans_silhouette: min_k must be an integer of at least 2")
        if isinstance(max_k, bool) or not isinstance(max_k, int) or max_k < min_k:
            raise StepError("esm_embedding_kmeans_silhouette: max_k must be an integer not below min_k")
        if max_k >= matrix.shape[0]:
            raise StepError(
                "esm_embedding_kmeans_silhouette: max_k must stay below the number of rows "
                f"({matrix.shape[0]})"
            )
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise StepError("esm_embedding_kmeans_silhouette: seed must be a non-negative integer")

        rows: list[list[float]] = []
        best = {"k": 0, "silhouette": -np.inf}
        labels_by_k: dict[str, list[int]] = {}
        for k in range(int(min_k), int(max_k) + 1):
            labels, inertia = kmeans(matrix, k, seed=int(seed))
            score = silhouette(matrix, labels)
            rows.append([float(score), inertia])
            labels_by_k[str(k)] = [int(value) for value in labels]
            if score > float(best["silhouette"]):
                best = {"k": k, "silhouette": score}

        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[cluster_dim, "statistic"],
            labels={
                cluster_dim: {str(k): index for index, k in enumerate(range(int(min_k), int(max_k) + 1))},
                "statistic": {"silhouette": 0, "inertia": 1},
            },
            info={
                "missing_code": np.nan,
                "min_k": int(min_k),
                "max_k": int(max_k),
                "seed": int(seed),
                "best_k": int(best["k"]),
                "best_silhouette": float(best["silhouette"]),
                "labels_by_k": labels_by_k,
                "n_samples": int(matrix.shape[0]),
                "embedding_dim": int(matrix.shape[1]),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "min_k": int(min_k),
            "max_k": int(max_k),
            "best_k": int(best["k"]),
            "best_silhouette": float(best["silhouette"]),
            "n_samples": int(matrix.shape[0]),
        }
        print(
            f"[esm_embedding_kmeans_silhouette] k {min_k}-{max_k}, "
            f"best k={best['k']} silhouette {float(best['silhouette']):.3f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
