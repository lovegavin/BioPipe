"""Locally linear embedding (LLE) of samples.

Uses sklearn.manifold.LocallyLinearEmbedding with a fixed
n_neighbors graph. The standard, modified, ltsa and hessian
algorithms are exposed; hessian may be numerically delicate on
small matrices."""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class LocallyLinearEmbeddingStep(Step):
    name = "locally_linear_embedding"
    title = "Locally linear embedding"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
                "sample_dim": {
                        "type": "string",
                        "default": "sample"
                },
                "feature_dim": {
                        "type": "string",
                        "default": "feature"
                },
                "n_components": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 2
                },
                "n_neighbors": {
                        "type": "integer",
                        "minimum": 2,
                        "default": 5
                },
                "method": {
                        "type": "string",
                        "enum": [
                                "standard",
                                "modified",
                                "ltsa",
                                "hessian"
                        ],
                        "default": "standard"
                },
                "random_state": {
                        "type": "integer",
                        "default": 0
                },
                "output": {
                        "type": "string"
                }
        },
        "required": [],
        "additionalProperties": False
}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        if X.shape[0] < 4:
            raise StepError("locally_linear_embedding needs at least four samples")
        n = int(ctx.step_params.get("n_components", 2))
        k = int(ctx.step_params.get("n_neighbors", 5))
        if n >= X.shape[0]:
            raise StepError("locally_linear_embedding: n_components must be smaller than n_samples")
        if k >= X.shape[0]:
            raise StepError("locally_linear_embedding: n_neighbors must be smaller than n_samples")
        from sklearn.manifold import LocallyLinearEmbedding
        model = LocallyLinearEmbedding(
            n_components=int(ctx.step_params.get("n_components", 2)),
            n_neighbors=int(ctx.step_params.get("n_neighbors", 5)),
            method=ctx.step_params.get("method", "standard"),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        embedded = model.fit_transform(X)
        projection(ctx, ctx.step_params.get("output", self.name), embedded,
                   sample_dim, samples, "LLE")
        self._export = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": int(embedded.shape[1]),
        }
        print(f"[locally_linear_embedding] {X.shape[0]} samples, {X.shape[1]} features -> {embedded.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export
