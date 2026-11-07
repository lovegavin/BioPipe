"""kNN density novelty scores for an embedding matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def density_scores(data: np.ndarray, *, k: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Return mean distance to the k nearest neighbours and outlier flags."""

    if data.size == 0:
        raise StepError("esm_embedding_knn_density: the embedding form is empty")
    if data.shape[0] < k + 1:
        raise StepError(f"esm_embedding_knn_density: at least {k + 1} samples are required for k={k}")
    if not np.isfinite(data).all():
        raise StepError("esm_embedding_knn_density: the embedding matrix contains non-finite values")
    try:
        from sklearn.neighbors import NearestNeighbors
    except ImportError:
        raise StepError("esm_embedding_knn_density: scikit-learn is required; install it with 'python -m pip install scikit-learn'") from None
    values = np.asarray(data, dtype=np.float64)
    model = NearestNeighbors(n_neighbors=int(k) + 1).fit(values)
    distances, _indices = model.kneighbors(values)
    mean_distance = distances[:, 1:].mean(axis=1)
    median = float(np.median(mean_distance))
    mad = float(np.median(np.abs(mean_distance - median))) or 1e-6
    z = (mean_distance - median) / (1.4826 * mad)
    flags = (z > 3.5).astype(np.int64)
    return mean_distance, flags


class EsmEmbeddingKnnDensityStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_knn_density.EsmEmbeddingKnnDensityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_knn_density",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding kNN density",
        "category": "Machine Learning",
        "icon": "ChartScatter",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sample_dim"}, {"param": "feature_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        sample_dim = params["sample_dim"]
        feature_dim = params["feature_dim"]
        if list(form.dims) != [sample_dim, feature_dim]:
            raise StepError(f"esm_embedding_knn_density: expected a [{sample_dim!r}, {feature_dim!r}] embedding form, got {list(form.dims)!r}")
        k = int(params.get("k", 5))
        scores, flags = density_scores(np.asarray(form.data, dtype=np.float64), k=k)
        data = np.column_stack([scores, flags.astype(np.float64)]).astype(np.float32)
        ctx[params.get("output", "density")] = Form(
            data=data,
            dims=["sample", "statistic"],
            labels={"sample": dict(form.labels[sample_dim]), "statistic": {"mean_distance": 0, "outlier": 1}},
            info={"missing_code": np.nan, "k": k, "n_outliers": int(flags.sum()), "n_samples": int(len(scores)), "median_distance": float(np.median(scores))},
        )
        self._export_data = {"n_outliers": int(flags.sum()), "k": k}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
