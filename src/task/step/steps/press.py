"""Prediction error sum of squares (PRESS) for an OLS fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class PressStep(Step):
    name = "press"
    title = "Prediction error sum of squares"
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
        samples, predictors, _, _, residuals, leverage, _, _, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, self.name
        )
        deleted = residuals / (1.0 - leverage)
        press = float(np.sum(deleted * deleted))
        n = len(samples)
        rmse = float(np.sqrt(press / n))
        form = Form(
            data=np.asarray([[press, rmse, float(n), float(p)]], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"press": 0},
                "statistic": {"press": 0, "press_rmse": 1, "n": 2, "p": 3},
            },
            info={"missing_code": np.nan, "response": response, "predictors": predictors},
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export_data = {
            "press": press,
            "press_rmse": rmse,
            "n": int(n),
            "p": int(p),
            "response": response,
        }
        print(f"[press] n={n}, PRESS={press:.4g}, RMSE={rmse:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
