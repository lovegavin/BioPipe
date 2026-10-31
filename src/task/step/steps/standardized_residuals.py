"""Standardized residuals for an ordinary least-squares fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class StandardizedResidualsStep(Step):
    name = "standardized_residuals"
    title = "Standardized residuals"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["response"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response = ctx.step_params["response"]
        samples, predictors, _, _, residuals, leverage, mse, _, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, self.name
        )
        values = residuals / np.sqrt(mse * (1.0 - leverage))
        form = Form(
            data=np.asarray(values, dtype=np.float64).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "metric": {"standardized_residual": 0},
            },
            info={"missing_code": np.nan, "response": response, "predictors": predictors, "p": int(p)},
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export_data = {
            "n": len(samples),
            "p": int(p),
            "response": response,
            "max_abs_standardized_residual": float(np.max(np.abs(values))),
            "max_sample": samples[int(np.argmax(np.abs(values)))],
        }
        print(f"[standardized_residuals] n={len(samples)}, max|z|={np.max(np.abs(values)):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
