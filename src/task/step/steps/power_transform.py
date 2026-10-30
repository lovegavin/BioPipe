"""Yeo-Johnson or Box-Cox power transform of each feature."""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import PowerTransformer

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class PowerTransformStep(Step):
    name = "power_transform"
    title = "Power transform"
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
            "method": {"type": "string", "enum": ["yeo-johnson", "box-cox"], "default": "yeo-johnson"},
            "standardize": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x, samples, features = matrix(form, sample_dim, feature_dim)
        method = ctx.step_params.get("method", "yeo-johnson")
        if method == "box-cox" and np.any(x <= 0):
            raise StepError("box-cox requires strictly positive values")
        transformer = PowerTransformer(method=method, standardize=bool(ctx.step_params.get("standardize", True)))
        transformed = transformer.fit_transform(x)
        axis = form.dims.index(sample_dim)
        data = np.moveaxis(transformed, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "power", "method": method},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "method": method}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
