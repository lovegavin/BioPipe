"""Independent component analysis of a sample x feature matrix."""
from __future__ import annotations


from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class IcaStep(Step):
    name = "ica"
    title = "ICA"
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
            "whiten": {"type": "string", "enum": ["unit-variance", "arbitrary"], "default": "unit-variance"},
            "max_iter": {"type": "integer", "minimum": 10, "default": 500},
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
        k = int(ctx.step_params.get("n_components", 2))
        if k > min(X.shape):
            raise StepError(f"ica: n_components ({k}) exceeds min(n_samples, n_features) ({min(X.shape)})")
        from sklearn.decomposition import FastICA
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        out = FastICA(
            n_components=k,
            whiten=ctx.step_params.get("whiten", "unit-variance"),
            max_iter=int(ctx.step_params.get("max_iter", 500)),
            random_state=int(ctx.step_params.get("random_state", 0)),
        ).fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "IC")
        self._export_data = {"n_samples": int(X.shape[0]), "n_features": int(X.shape[1]), "n_components": k}
        print(f"[ica] {X.shape[0]}x{X.shape[1]} -> {k} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
