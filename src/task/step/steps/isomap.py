"""Projection operator based on scikit-learn's Isomap."""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class IsomapStep(Step):
    name = "isomap"
    title = "Isomap"
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
            "n_components": {"type": "integer", "minimum": 2, "default": 2},
            "n_neighbors": {"type": "integer", "minimum": 2, "default": 5},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        k = int(ctx.step_params.get("n_components", 2))
        if k < 1:
            raise StepError("n_components must be >= 1")
        from sklearn.manifold import Isomap
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        model = Isomap(
            n_components=k,
            n_neighbors=min(int(ctx.step_params.get("n_neighbors", 5)), X.shape[0] - 1),
        )
        out = model.fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "Isomap")
        self._export_data = {"n_samples": int(X.shape[0]), "n_components": int(out.shape[1])}
        print(f"[isomap] {X.shape[0]}x{X.shape[1]} -> {out.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
