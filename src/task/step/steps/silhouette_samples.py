"""Per-sample silhouette coefficients."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import silhouette_samples

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix
from ._metric_common import label_series


class SilhouetteSamplesStep(Step):
    """Silhouette coefficient for each sample in a clustering."""

    name = "silhouette_samples"
    title = "Silhouette samples"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "label_dim": {"type": "string", "default": "label"},
            "target_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        feature_form, label_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        X, samples, _ = matrix(feature_form, sample_dim, feature_dim)
        label_samples, labels = label_series(
            label_form, sample_dim, label_dim, ctx.step_params["target_label"], "silhouette_samples"
        )
        pos = {name: i for i, name in enumerate(label_samples)}
        keep = [i for i, name in enumerate(samples) if name in pos]
        if len(keep) < 4:
            raise StepError("silhouette_samples: fewer than four shared samples")
        y = [labels[pos[samples[i]]] for i in keep]
        if any(value is None for value in y):
            raise StepError("silhouette_samples: cluster labels must not be missing")
        classes = sorted(set(y))
        if len(classes) < 2:
            raise StepError("silhouette_samples: need at least two clusters")
        if min(y.count(cluster) for cluster in classes) < 2:
            raise StepError("silhouette_samples: each cluster needs at least two samples")
        scores = silhouette_samples(X[keep], y)
        kept_samples = [samples[i] for i in keep]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(scores, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={"sample": {name: i for i, name in enumerate(kept_samples)}, "metric": {"silhouette": 0}},
            info={"missing_code": np.nan, "metric": "euclidean"},
        )
        self._export_data = {
            "n_samples": len(keep),
            "n_clusters": len(classes),
            "metric": "euclidean",
            "silhouette": {name: float(score) for name, score in zip(kept_samples, scores)},
            "clusters": {name: label for name, label in zip(kept_samples, y)},
        }
        print(f"[silhouette_samples] n={len(keep)}, k={len(classes)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
