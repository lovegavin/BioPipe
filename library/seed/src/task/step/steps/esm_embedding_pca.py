"""Principal-component projection of ESM embeddings."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

MAX_COMPONENTS = 50


def pca_projection(matrix: np.ndarray, n_components: int) -> dict:
    """Project ``matrix`` onto its leading principal components (SVD based)."""
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2:
        raise StepError("esm_embedding_pca: the embedding matrix must be two-dimensional")
    if not np.isfinite(values).all():
        raise StepError("esm_embedding_pca: the embedding matrix contains non-finite values")
    rows, columns = values.shape
    limit = min(rows - 1, columns, MAX_COMPONENTS)
    if n_components > limit:
        raise StepError(
            f"esm_embedding_pca: n_components must be at most {limit} for a "
            f"{rows} x {columns} matrix, got {n_components}"
        )
    mean = values.mean(axis=0)
    centered = values - mean
    _, singular_values, components = np.linalg.svd(centered, full_matrices=False)
    scores = centered @ components[:n_components].T
    variance = singular_values**2
    total = float(variance.sum())
    if total <= 0.0:
        raise StepError(
            "esm_embedding_pca: the embedding matrix has no variance to project"
        )
    return {
        "scores": scores.astype(np.float32),
        "components": components[:n_components].astype(np.float32),
        "singular_values": singular_values[:n_components].astype(np.float32),
        "explained_variance_ratio": (variance[:n_components] / total).astype(np.float32),
        "mean": mean.astype(np.float32),
        "total_variance": total,
    }


class EsmEmbeddingPcaStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_pca.EsmEmbeddingPcaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_pca",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM embedding PCA",
        "category": "Machine Learning",
        "icon": "GridNine",
        "description": (
            "Project an ESM embedding matrix onto its leading principal "
            "components for visualisation and clustering."
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
        out_name = params["output"]
        if not inputs:
            raise StepError("esm_embedding_pca: an embedding form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, embedding_dim]:
            raise StepError(
                "esm_embedding_pca: the input must have dims "
                f"[{sequence_dim}, {embedding_dim}], got {list(form.dims)}"
            )
        if form.data.shape[0] < 2:
            raise StepError(
                "esm_embedding_pca: at least two sequences are required to project components"
            )
        raw_components = params.get("n_components")
        n_components = 2 if raw_components is None else int(raw_components)
        if n_components < 1:
            raise StepError("esm_embedding_pca: n_components must be positive")
        projection = pca_projection(form.data, n_components)
        labels = {
            sequence_dim: dict(form.labels.get(sequence_dim) or {}),
            "component": {
                f"PC{index + 1}": index for index in range(n_components)
            },
        }
        if len(labels[sequence_dim]) != form.data.shape[0]:
            labels[sequence_dim] = {
                str(index + 1): index for index in range(form.data.shape[0])
            }
        output = Form(
            data=projection["scores"],
            dims=[sequence_dim, "component"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_sequences": int(form.data.shape[0]),
                "embedding_dim": int(form.data.shape[1]),
                "n_components": n_components,
                "explained_variance_ratio": [
                    float(value) for value in projection["explained_variance_ratio"]
                ],
                "singular_values": [
                    float(value) for value in projection["singular_values"]
                ],
                "components": projection["components"].tolist(),
                "mean": projection["mean"].tolist(),
                "total_variance": projection["total_variance"],
            },
        )
        output.validate()
        ctx[out_name] = output
        ratio = float(projection["explained_variance_ratio"].sum())
        self._export_data = {
            "n_sequences": int(form.data.shape[0]),
            "embedding_dim": int(form.data.shape[1]),
            "n_components": n_components,
            "explained_variance_ratio": [
                float(value) for value in projection["explained_variance_ratio"]
            ],
            "cumulative_explained_variance": ratio,
        }
        print(
            f"[esm_embedding_pca] {form.data.shape[0]} x {form.data.shape[1]} -> "
            f"{n_components} components, {ratio:.4f} variance"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
