"""t-SNE embedding.

Projects samples into two (or three) non-linear components. The
implementation calls scikit-learn's exact t-SNE; it is intended for
small and medium matrices, not for atlas-scale data.
"""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class TsneStep(Step):
    name = "tsne"
    title = "t-SNE"
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
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "n_components": {"type": "integer", "minimum": 2, "maximum": 3, "default": 2},
            "perplexity": {"type": "number", "exclusiveMinimum": 1, "default": 30.0},
            "learning_rate": {"type": ["number", "string"], "default": "auto"},
            "max_iter": {"type": "integer", "minimum": 250, "default": 1000},
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
        if X.shape[0] < 3:
            raise StepError("tsne needs at least three samples")
        n = int(ctx.step_params.get("n_components", 2))
        perplexity = float(ctx.step_params.get("perplexity", 30.0))
        if perplexity >= X.shape[0]:
            raise StepError(
                f"tsne: perplexity ({perplexity}) must be smaller than n_samples ({X.shape[0]})"
            )
        from sklearn.manifold import TSNE
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        out = TSNE(
            n_components=n,
            perplexity=perplexity,
            learning_rate=ctx.step_params.get("learning_rate", "auto"),
            max_iter=int(ctx.step_params.get("max_iter", 1000)),
            random_state=int(ctx.step_params.get("random_state", 0)),
            init="pca",
        ).fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "TSNE")
        self._export_data = {"n_samples": int(X.shape[0]), "n_components": n, "perplexity": perplexity}
        print(f"[tsne] {X.shape[0]} samples -> {n} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
