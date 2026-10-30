from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix

class DbscanStep(Step):
    """Density-based spatial clustering (DBSCAN)."""

    name = "dbscan"
    title = "DBSCAN clustering"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"

    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
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
            "eps": {"type": "number", "exclusiveMinimum": 0, "default": 0.5},
            "min_samples": {"type": "integer", "minimum": 2, "default": 5},
            "metric": {"type": "string", "enum": ["euclidean", "manhattan", "cosine"], "default": "euclidean"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.cluster import DBSCAN

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        eps = float(ctx.step_params.get("eps", 0.5))
        min_samples = int(ctx.step_params.get("min_samples", 5))
        metric = ctx.step_params.get("metric", "euclidean")
        if eps <= 0:
            raise StepError("dbscan: eps must be > 0")
        if min_samples < 2:
            raise StepError("dbscan: min_samples must be >= 2")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
        labels = model.fit_predict(X)
        n_clusters = len(set(labels.tolist())) - (1 if -1 in labels else 0)
        samples = list(sample_names)
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=labels.astype(np.float32).reshape(-1, 1),
            dims=[sample_dim, "cluster"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "cluster": {"cluster": 0},
            },
            info={"missing_code": np.nan},
        )

        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_clusters": n_clusters,
            "n_noise": int((labels == -1).sum()),
            "eps": eps,
            "min_samples": min_samples,
        }
        print(f"[dbscan] {len(sample_names)} samples -> {n_clusters} clusters, {int((labels == -1).sum())} noise")

    def export(self, ctx: Context) -> dict:
        return self._export_data
