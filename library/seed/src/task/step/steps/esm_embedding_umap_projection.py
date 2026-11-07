"""Spectral embedding of an ESM embedding Form (UMAP-style kNN graph)."""

from __future__ import annotations

import numpy as np
from scipy import linalg

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def knn_graph(matrix: np.ndarray, k: int) -> np.ndarray:
    """Binary symmetric k-nearest-neighbour adjacency."""
    rows = matrix.shape[0]
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise StepError("esm_embedding_umap_projection: k must be a positive integer")
    limit = min(rows - 1, 50)
    if k > limit:
        raise StepError(f"esm_embedding_umap_projection: k must be at most {limit}")
    distances = np.linalg.norm(matrix[:, None, :] - matrix[None, :, :], axis=-1)
    np.fill_diagonal(distances, np.inf)
    neighbours = np.argsort(distances, axis=1)[:, :k]
    graph = np.zeros((rows, rows), dtype=np.float64)
    for source in range(rows):
        for target in neighbours[source]:
            graph[source, int(target)] = 1.0
            graph[int(target), source] = 1.0
    return graph


def spectral_embedding(matrix: np.ndarray, k: int = 8, components: int = 2) -> np.ndarray:
    """Normalised-Laplacian spectral embedding with deterministic signs."""
    graph = knn_graph(matrix, k)
    degree = graph.sum(axis=1)
    inverted = np.zeros_like(degree)
    positive = degree > 0.0
    inverted[positive] = 1.0 / np.sqrt(degree[positive])
    laplacian = np.eye(graph.shape[0]) - (inverted[:, None] * graph * inverted[None, :])
    values, vectors = linalg.eigh(laplacian)
    order = np.argsort(values)
    picked = order[1 : components + 1]
    embedding = vectors[:, picked]
    for column in range(embedding.shape[1]):
        pivot = int(np.argmax(np.abs(embedding[:, column])))
        if embedding[pivot, column] < 0.0:
            embedding[:, column] = -embedding[:, column]
    return embedding


class EsmEmbeddingUmapProjectionStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_umap_projection.EsmEmbeddingUmapProjectionStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "esm_embedding_umap_projection",
        "kind": "operator",
        "title": "Embedding spectral projection",
        "description": "Project an embedding Form with a kNN graph and the eigenvectors of its normalised Laplacian, giving a deterministic UMAP-style two-dimensional layout.",
        "category": "Machine Learning",
        "icon": "ChartScatter",
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
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("esm_embedding_umap_projection: an embedding form input is required")
        form = inputs[0]
        sequence_dim = str(ctx.step_params.get("sequence_dim", "sequence") or "sequence")
        embedding_dim = str(ctx.step_params.get("embedding_dim", "embedding") or "embedding")
        component_dim = str(ctx.step_params.get("component_dim", "component") or "component")
        out_name = ctx.step_params.get("output", "projection") or "projection"
        neighbours = ctx.step_params.get("n_neighbors", 8)
        components = ctx.step_params.get("n_components", 2)

        if list(form.dims) != [sequence_dim, embedding_dim]:
            raise StepError(
                "esm_embedding_umap_projection: an embedding form with dims "
                f"[{sequence_dim}, {embedding_dim}] is required, got {list(form.dims)}"
            )
        matrix = np.asarray(form.data, dtype=np.float64)
        if not np.all(np.isfinite(matrix)):
            raise StepError("esm_embedding_umap_projection: the embedding matrix contains non-finite values")
        if matrix.shape[0] < 4:
            raise StepError("esm_embedding_umap_projection: at least four sequences are required")
        if isinstance(components, bool) or not isinstance(components, int) or not 2 <= components <= 3:
            raise StepError("esm_embedding_umap_projection: n_components must be 2 or 3")

        embedding = spectral_embedding(matrix, int(neighbours), int(components))
        labels = form.labels.get(sequence_dim) or {}
        order = sorted(labels, key=lambda label: labels[label])
        row_labels = [str(label) for label in order]
        component_labels = [f"axis{index + 1}" for index in range(embedding.shape[1])]
        out = Form(
            data=embedding.astype(np.float32),
            dims=[sequence_dim, component_dim],
            labels={
                sequence_dim: {label: index for index, label in enumerate(row_labels)},
                component_dim: {label: index for index, label in enumerate(component_labels)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": int(matrix.shape[0]),
                "embedding_dim": int(matrix.shape[1]),
                "n_neighbors": int(neighbours),
                "n_components": int(components),
                "method": "normalised-laplacian-spectral",
                "component_labels": component_labels,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": int(matrix.shape[0]),
            "embedding_dim": int(matrix.shape[1]),
            "n_components": int(components),
            "spread": [float(embedding[:, column].std()) for column in range(embedding.shape[1])],
        }
        print(
            f"[esm_embedding_umap_projection] {matrix.shape[0]} sequences, "
            f"{components} components, k={neighbours}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
