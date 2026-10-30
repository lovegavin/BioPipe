from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix

class AgglomerativeStep(Step):
    """Agglomerative (hierarchical) clustering."""

    name = "agglomerative"
    title = "Agglomerative clustering"
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
            "n_clusters": {"type": "integer", "minimum": 2, "default": 2},
            "linkage": {"type": "string", "enum": ["ward", "complete", "average", "single"], "default": "ward"},
            "metric": {"type": "string", "enum": ["euclidean", "manhattan", "cosine"], "default": "euclidean"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.cluster import AgglomerativeClustering

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_clusters = int(ctx.step_params.get("n_clusters", 2))
        linkage = ctx.step_params.get("linkage", "ward")
        metric = ctx.step_params.get("metric", "euclidean")
        if n_clusters < 2:
            raise StepError("agglomerative: n_clusters must be >= 2")
        if linkage == "ward" and metric != "euclidean":
            raise StepError("agglomerative: ward linkage requires euclidean metric")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage, metric=metric)
        labels = model.fit_predict(X)
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
            "n_clusters": int(n_clusters),
            "linkage": linkage,
            "metric": metric,
        }
        print(f"[agglomerative] {len(sample_names)} samples -> {n_clusters} clusters")

    def export(self, ctx: Context) -> dict:
        return self._export_data
