"""Projection operator based on scikit-learn's Kernel PCA."""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class KernelPcaStep(Step):
    name = "kernel_pca"
    title = "Kernel PCA"
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
            "n_components": {"type": "integer", "minimum": 1, "default": 2},
            "kernel": {"type": "string", "enum": ["rbf", "linear", "poly", "sigmoid", "cosine"], "default": "rbf"},
            "gamma": {"type": ["number", "null"], "exclusiveMinimum": 0, "default": None},
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
        from sklearn.decomposition import KernelPCA
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        model = KernelPCA(
            n_components=k,
            kernel=ctx.step_params.get("kernel", "rbf"),
            gamma=ctx.step_params.get("gamma"),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        out = model.fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "KPC")
        self._export_data = {"n_samples": int(X.shape[0]), "n_components": int(out.shape[1])}
        print(f"[kernel_pca] {X.shape[0]}x{X.shape[1]} -> {out.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
