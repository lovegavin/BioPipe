"""PCA loadings for an ESM embedding matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

MAX_COMPONENTS = 50


def pca_loadings(matrix: np.ndarray, n_components: int) -> dict:
    """Return component loadings (feature x component) from an SVD."""
    data = np.asarray(matrix, dtype=np.float64)
    if data.ndim != 2:
        raise StepError("esm_embedding_pca_loadings: the embedding matrix must be two-dimensional")
    rows, columns = data.shape
    if rows < 2:
        raise StepError("esm_embedding_pca_loadings: at least two embeddings are required")
    limit = min(rows - 1, columns, MAX_COMPONENTS)
    if n_components < 1 or n_components > limit:
        raise StepError(
            f"esm_embedding_pca_loadings: n_components must be between 1 and {limit}"
        )
    mean = data.mean(axis=0)
    centered = data - mean
    u, singular, vt = np.linalg.svd(centered, full_matrices=False)
    variance = singular ** 2
    total = float(variance.sum())
    if total <= 0:
        raise StepError("esm_embedding_pca_loadings: the embedding matrix has no variance")
    components = vt[:n_components]
    loadings = components.T * np.sqrt(variance[:n_components] / max(rows - 1, 1))
    return {
        "loadings": loadings.astype(np.float64),
        "components": components,
        "singular_values": singular[:n_components],
        "explained_variance_ratio": (variance[:n_components] / total),
        "mean": mean,
        "total_variance": total,
        "limit": limit,
    }


class EsmEmbeddingPcaLoadingsStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_pca_loadings.EsmEmbeddingPcaLoadingsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_pca_loadings",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding PCA loadings",
        "description": "Projects embeddings on principal components and reports per-feature loadings.",
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "sequence_dim", "default": "sequence"},
                    {"param": "embedding_dim", "default": "embedding"},
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2,
            }],
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        embedding_dim = str(params.get("embedding_dim") or "embedding")
        n_components = int(params.get("n_components", 2))
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, embedding_dim]:
            raise StepError(
                f"esm_embedding_pca_loadings: an embedding form with dims "
                f"[{sequence_dim}, {embedding_dim}] is required, got {list(form.dims)}"
            )
        data = np.asarray(form.data, dtype=np.float64)
        if not np.all(np.isfinite(data)):
            raise StepError("esm_embedding_pca_loadings: the embedding matrix contains non-finite values")

        result = pca_loadings(data, n_components)
        loadings = result["loadings"]
        features = [str(label) for label in form.labels.get(embedding_dim, {})] or [
            str(index) for index in range(loadings.shape[0])
        ]
        components = [f"PC{index + 1}" for index in range(loadings.shape[1])]
        output = Form(
            data=loadings.astype(np.float32),
            dims=[embedding_dim, "component"],
            labels={
                embedding_dim: {name: index for index, name in enumerate(features)},
                "component": {name: index for index, name in enumerate(components)},
            },
            info={
                "missing_code": float("nan"),
                "n_embeddings": int(data.shape[0]),
                "embedding_dim": int(data.shape[1]),
                "n_components": len(components),
                "explained_variance_ratio": [float(value) for value in result["explained_variance_ratio"]],
                "singular_values": [float(value) for value in result["singular_values"]],
                "components": result["components"].tolist(),
                "mean": result["mean"].tolist(),
                "total_variance": float(result["total_variance"]),
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_embeddings": int(data.shape[0]),
            "embedding_dim": int(data.shape[1]),
            "n_components": len(components),
            "explained_variance_ratio": [float(value) for value in result["explained_variance_ratio"]],
        }
        print(
            f"[esm_embedding_pca_loadings] {data.shape[0]} embeddings x {data.shape[1]} features, "
            f"{len(components)} components, first ratio "
            f"{self._export_data['explained_variance_ratio'][0]:.4f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
