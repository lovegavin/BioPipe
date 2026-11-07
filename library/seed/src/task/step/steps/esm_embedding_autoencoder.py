"""Embedding autoencoder reconstruction errors."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def _build(features: int, hidden: int, latent: int, seed: int) -> nn.Module:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    return nn.Sequential(
        nn.Linear(features, hidden),
        nn.ReLU(),
        nn.Linear(hidden, latent),
        nn.ReLU(),
        nn.Linear(latent, hidden),
        nn.ReLU(),
        nn.Linear(hidden, features),
    )


def reconstruction_errors(
    data: np.ndarray,
    *,
    hidden: int = 8,
    latent: int = 2,
    epochs: int = 200,
    learning_rate: float = 0.01,
    random_state: int = 0,
) -> tuple[np.ndarray, float]:
    """Train a small autoencoder and return per-sample MSE plus final loss."""

    if data.size == 0:
        raise StepError("esm_embedding_autoencoder: the embedding form is empty")
    if latent < 1:
        raise StepError("esm_embedding_autoencoder: latent must be at least 1")
    if not np.isfinite(data).all():
        raise StepError("esm_embedding_autoencoder: the embedding matrix contains non-finite values")
    import torch

    features = int(data.shape[1])
    model = _build(features, int(hidden), int(latent), int(random_state))
    optimiser = torch.optim.Adam(model.parameters(), lr=float(learning_rate))
    tensor = torch.as_tensor(np.asarray(data, dtype=np.float32))
    final = float("nan")
    for _ in range(int(epochs)):
        optimiser.zero_grad()
        reconstructed = model(tensor)
        loss = torch.mean((reconstructed - tensor) ** 2)
        loss.backward()
        optimiser.step()
        final = float(loss.detach())
    with torch.no_grad():
        errors = torch.mean((model(tensor) - tensor) ** 2, dim=1).cpu().numpy().astype(np.float64)
    return errors, final


class EsmEmbeddingAutoencoderStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_autoencoder.EsmEmbeddingAutoencoderStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_autoencoder",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding autoencoder",
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sample_dim"}, {"param": "feature_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False},
            },
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
            raise StepError(
                f"esm_embedding_autoencoder: expected a [{sample_dim!r}, {feature_dim!r}] embedding form, got {list(form.dims)!r}"
            )
        data = np.asarray(form.data, dtype=np.float64)
        errors, final = reconstruction_errors(
            data,
            hidden=int(params.get("hidden", 8)),
            latent=int(params.get("latent", 2)),
            epochs=int(params.get("epochs", 200)),
            learning_rate=float(params.get("learning_rate", 0.01)),
            random_state=int(params.get("random_state", 0)),
        )
        means = errors.mean()
        std = errors.std()
        out_name = params.get("output", "errors")
        labels = {label: position for label, position in form.labels[sample_dim].items()}
        ctx[out_name] = Form(
            data=errors.reshape(-1, 1).astype(np.float32),
            dims=["sample", "statistic"],
            labels={"sample": labels, "statistic": {"reconstruction_mse": 0}},
            info={
                "missing_code": np.nan,
                "mean_error": float(means),
                "std_error": float(std),
                "final_loss": float(final),
                "n_samples": int(data.shape[0]),
                "n_features": int(data.shape[1]),
                "hidden": int(params.get("hidden", 8)),
                "latent": int(params.get("latent", 2)),
                "epochs": int(params.get("epochs", 200)),
            },
        )
        self._export_data = {"n_samples": int(data.shape[0]), "mean_error": float(means)}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
