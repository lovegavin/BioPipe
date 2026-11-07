"""Nearest-neighbour retrieval in an ESM embedding space."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

MAX_NEIGHBORS = 50


def similarity_matrix(matrix: np.ndarray, metric: str) -> np.ndarray:
    """Return a square similarity matrix (larger is closer) for ``metric``."""
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2:
        raise StepError(
            "esm_embedding_neighbors: the embedding matrix must be two-dimensional"
        )
    if not np.isfinite(values).all():
        raise StepError(
            "esm_embedding_neighbors: the embedding matrix contains non-finite values"
        )
    if metric == "cosine":
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        if np.any(norms == 0.0):
            raise StepError(
                "esm_embedding_neighbors: cosine similarity needs non-zero embedding rows"
            )
        normalized = values / norms
        return normalized @ normalized.T
    if metric == "euclidean":
        squared = (
            np.sum(values**2, axis=1, keepdims=True)
            + np.sum(values**2, axis=1, keepdims=True).T
            - 2.0 * values @ values.T
        )
        distances = np.sqrt(np.clip(squared, 0.0, None))
        return -distances
    raise StepError(
        f"esm_embedding_neighbors: metric must be 'cosine' or 'euclidean', got '{metric}'"
    )


def neighbor_indices(similarity: np.ndarray, k: int) -> np.ndarray:
    """Return the ``k`` nearest neighbours per row, excluding the row itself."""
    rows = similarity.shape[0]
    if k < 1:
        raise StepError("esm_embedding_neighbors: k must be positive")
    if k > min(rows - 1, MAX_NEIGHBORS):
        raise StepError(
            f"esm_embedding_neighbors: k must be at most {min(rows - 1, MAX_NEIGHBORS)} "
            f"for {rows} sequences, got {k}"
        )
    working = similarity.copy()
    np.fill_diagonal(working, -np.inf)
    return np.argsort(-working, axis=1)[:, :k]


class EsmEmbeddingNeighborsStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_neighbors.EsmEmbeddingNeighborsStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_neighbors",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM embedding neighbours",
        "category": "Machine Learning",
        "icon": "GridNine",
        "description": (
            "Retrieve the k nearest neighbours of every sequence in an ESM "
            "embedding matrix using cosine similarity or euclidean distance."
        ),
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "embedding_dim", "default": "embedding"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "version": 1,
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        embedding_dim = str(params.get("embedding_dim") or "embedding")
        neighbor_dim = str(params.get("neighbor_dim") or "neighbor")
        metric = str(params.get("metric") or "cosine")
        out_name = params["output"]
        if metric not in {"cosine", "euclidean"}:
            raise StepError(
                "esm_embedding_neighbors: metric must be 'cosine' or 'euclidean'"
            )
        if not inputs:
            raise StepError("esm_embedding_neighbors: an embedding form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, embedding_dim]:
            raise StepError(
                "esm_embedding_neighbors: the input must have dims "
                f"[{sequence_dim}, {embedding_dim}], got {list(form.dims)}"
            )
        rows = form.data.shape[0]
        if rows < 2:
            raise StepError(
                "esm_embedding_neighbors: at least two sequences are required"
            )
        raw_k = params.get("k")
        k = 1 if raw_k is None else int(raw_k)
        similarity = similarity_matrix(form.data, metric)
        indices = neighbor_indices(similarity, k)
        values = np.take_along_axis(similarity, indices, axis=1)
        if metric == "euclidean":
            values = -values
        labels = dict(form.labels.get(sequence_dim) or {})
        if len(labels) != rows:
            labels = {str(index + 1): index for index in range(rows)}
        by_index = {position: label for label, position in labels.items()}
        neighbors = [
            [by_index.get(int(index), str(index + 1)) for index in row]
            for row in indices
        ]
        output = Form(
            data=np.asarray(values, dtype=np.float32),
            dims=[sequence_dim, neighbor_dim],
            labels={
                sequence_dim: labels,
                neighbor_dim: {str(index + 1): index for index in range(k)},
            },
            info={
                "missing_code": np.nan,
                "metric": metric,
                "k": k,
                "neighbors": neighbors,
                "similarity": metric == "cosine",
                "n_sequences": rows,
                "embedding_dim": int(form.data.shape[1]),
            },
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_sequences": rows,
            "k": k,
            "metric": metric,
            "neighbors": neighbors,
            "farthest_similarity": float(values.min()),
            "closest_similarity": float(values.max()),
        }
        print(
            f"[esm_embedding_neighbors] {rows} sequences, k={k}, metric {metric}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
