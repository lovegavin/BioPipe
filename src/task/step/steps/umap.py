"""UMAP embedding.

Projects samples into two or three non-linear components with umap-learn.
The implementation standardises features before fitting and is intended for
small and medium matrices, not atlas-scale data."""
from __future__ import annotations

from sklearn.preprocessing import StandardScaler
from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class UmapStep(Step):
    name = "umap"
    title = "UMAP"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["umap-learn>=0.5"]
    dependency_imports = ["umap"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "n_components": {"type": "integer", "minimum": 2, "maximum": 3, "default": 2},
            "n_neighbors": {"type": "integer", "minimum": 2, "default": 15},
            "min_dist": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.1},
            "metric": {"type": "string", "enum": ["euclidean", "cosine", "correlation", "manhattan"], "default": "euclidean"},
            "random_state": {"type": "integer", "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        n = int(ctx.step_params.get("n_components", 2))
        neighbors = int(ctx.step_params.get("n_neighbors", 15))
        if X.shape[0] < 3:
            raise StepError("umap needs at least three samples")
        neighbors = min(neighbors, X.shape[0] - 1)
        if neighbors < 2:
            raise StepError("umap needs at least two neighbours")
        from umap import UMAP

        Xs = StandardScaler().fit_transform(X)
        out = UMAP(
            n_components=n,
            n_neighbors=neighbors,
            min_dist=float(ctx.step_params.get("min_dist", 0.1)),
            metric=str(ctx.step_params.get("metric", "euclidean")),
            random_state=int(ctx.step_params.get("random_state", 0)),
        ).fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "UMAP")
        self._export = {"n_samples": int(X.shape[0]), "n_components": n, "n_neighbors": neighbors}
        print(f"[umap] {X.shape[0]} samples -> {n} components")

    def export(self, ctx: Context) -> dict:
        return self._export
