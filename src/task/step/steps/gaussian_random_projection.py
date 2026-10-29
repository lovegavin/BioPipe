"""Gaussian random projection of a feature matrix.

This is a fast, data-independent linear embedding. It is useful as
a cheap dimensionality reduction baseline before clustering."""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class GaussianRandomProjectionStep(Step):
    name = "gaussian_random_projection"
    title = "Gaussian random projection"
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
        n = int(ctx.step_params.get("n_components", 2))
        if n > X.shape[1]:
            raise StepError("gaussian_random_projection: n_components cannot exceed n_features")
        from sklearn.random_projection import GaussianRandomProjection
        model = GaussianRandomProjection(
            n_components=int(ctx.step_params.get("n_components", 2)),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        embedded = model.fit_transform(X)
        projection(ctx, ctx.step_params.get("output", self.name), embedded,
                   sample_dim, samples, "GRP")
        self._export = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": int(embedded.shape[1]),
        }
        print(f"[gaussian_random_projection] {X.shape[0]} samples, {X.shape[1]} features -> {embedded.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export
