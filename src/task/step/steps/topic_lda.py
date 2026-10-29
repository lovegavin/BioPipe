"""Latent Dirichlet allocation topic model for non-negative count data.

Each sample is a document and each feature is a token type. The
output is the sample-topic distribution. This operator is not a
gene-level LDA classifier; use lda_classifier for supervised LDA."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class TopicLdaStep(Step):
    name = "topic_lda"
    title = "Topic LDA"
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
                "max_iter": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 20
                },
                "learning_method": {
                        "type": "string",
                        "enum": [
                                "batch",
                                "online"
                        ],
                        "default": "batch"
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
        if np.any(X < 0):
            raise StepError("topic_lda requires non-negative input")
        if X.shape[0] < 2:
            raise StepError("topic_lda needs at least two samples")
        from sklearn.decomposition import LatentDirichletAllocation
        model = LatentDirichletAllocation(
            n_components=int(ctx.step_params.get("n_components", 2)),
            max_iter=int(ctx.step_params.get("max_iter", 20)),
            learning_method=ctx.step_params.get("learning_method", "batch"),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        embedded = model.fit_transform(X)
        projection(ctx, ctx.step_params.get("output", self.name), embedded,
                   sample_dim, samples, "Topic")
        self._export = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": int(embedded.shape[1]),
        }
        print(f"[topic_lda] {X.shape[0]} samples, {X.shape[1]} features -> {embedded.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export
