"""Quantile transform each feature to a normal or uniform distribution."""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import QuantileTransformer

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class QuantileTransformStep(Step):
    name = "quantile_transform"
    title = "Quantile transform"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn"]
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
            "n_quantiles": {"type": "integer", "minimum": 2, "default": 1000},
            "output_distribution": {"type": "string", "enum": ["normal", "uniform"], "default": "normal"},
            "random_state": {"type": "integer", "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x, samples, features = matrix(form, sample_dim, feature_dim)
        n_quantiles = min(int(ctx.step_params.get("n_quantiles", 1000)), x.shape[0])
        transformer = QuantileTransformer(
            n_quantiles=n_quantiles,
            output_distribution=ctx.step_params.get("output_distribution", "normal"),
            random_state=int(ctx.step_params.get("random_state", 0)),
            subsample=min(x.shape[0], 100000),
        )
        transformed = transformer.fit_transform(x)
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(transformed, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "quantile", "output_distribution": ctx.step_params.get("output_distribution", "normal")},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "n_quantiles": n_quantiles}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
