"""PCA reconstruction errors for an embedding matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def reconstruction_errors(data: np.ndarray, *, n_components: int = 2, standardize: bool = False) -> tuple[np.ndarray, float]:
    if data.size == 0:
        raise StepError("esm_embedding_pca_reconstruction: the embedding form is empty")
    if data.shape[0] < 2:
        raise StepError("esm_embedding_pca_reconstruction: at least two samples are required")
    if n_components < 1:
        raise StepError("esm_embedding_pca_reconstruction: n_components must be at least 1")
    if not np.isfinite(data).all():
        raise StepError("esm_embedding_pca_reconstruction: the embedding matrix contains non-finite values")
    values = np.asarray(data, dtype=np.float64)
    if standardize:
        std = values.std(axis=0)
        std[std == 0] = 1.0
        values = (values - values.mean(axis=0)) / std
    components = int(min(n_components, values.shape[0] - 1, values.shape[1]))
    mean = values.mean(axis=0)
    centred = values - mean
    _u, _s, vt = np.linalg.svd(centred, full_matrices=False)
    basis = vt[:components]
    reconstructed = (centred @ basis.T) @ basis + mean
    errors = ((reconstructed - values) ** 2).mean(axis=1)
    return errors, float(errors.mean())


class EsmEmbeddingPcaReconstructionStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_pca_reconstruction.EsmEmbeddingPcaReconstructionStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_pca_reconstruction",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding PCA reconstruction",
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
            raise StepError(f"esm_embedding_pca_reconstruction: expected a [{sample_dim!r}, {feature_dim!r}] embedding form, got {list(form.dims)!r}")
        errors, mean_error = reconstruction_errors(np.asarray(form.data, dtype=np.float64), n_components=int(params.get("n_components", 2)), standardize=bool(params.get("standardize", False)))
        ctx[params.get("output", "errors")] = Form(
            data=errors.reshape(-1, 1).astype(np.float32),
            dims=["sample", "statistic"],
            labels={"sample": dict(form.labels[sample_dim]), "statistic": {"reconstruction_mse": 0}},
            info={"missing_code": np.nan, "mean_error": mean_error, "n_samples": int(errors.size), "n_components": int(params.get("n_components", 2)), "standardize": bool(params.get("standardize", False))},
        )
        self._export_data = {"n_samples": int(errors.size), "mean_error": mean_error}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
