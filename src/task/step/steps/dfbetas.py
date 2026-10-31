"""Standardized DFBETAS for an ordinary least-squares fit."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class DfbetasStep(Step):
    name = "dfbetas"
    title = "Standardized DFBETAS"
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
        out_name = ctx.step_params.get("output", self.name)
        samples, predictors, _, design, residuals, leverage, _, s2_i, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, "dfbetas"
        )
        xtx_inverse = np.linalg.inv(design.T @ design)
        raw = (xtx_inverse @ (design.T * (residuals / (1.0 - leverage)))).T
        scale = np.sqrt(s2_i)[:, None] * np.sqrt(np.diag(xtx_inverse))[None, :]
        if np.any(scale <= 0):
            raise StepError("dfbetas: coefficient scale is not positive")
        standardized = raw / scale
        names = ["intercept"] + predictors
        form = Form(
            data=np.asarray(standardized, dtype=np.float32),
            dims=["sample", "coefficient"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "coefficient": {name: i for i, name in enumerate(names)},
            },
            info={
                "missing_code": np.nan,
                "response": response,
                "predictors": predictors,
                "p": int(p),
                "coefficient_order": names,
                "statistic": "dfbetas",
            },
        )
        form.validate()
        ctx[out_name] = form
        maximum = np.unravel_index(int(np.argmax(np.abs(standardized))), standardized.shape)
        self._export_data = {
            "n": len(samples),
            "p": int(p),
            "response": response,
            "predictors": predictors,
            "coefficients": names,
            "max_abs_dfbetas": float(abs(standardized[maximum])),
            "max_sample": samples[maximum[0]],
            "max_coefficient": names[maximum[1]],
        }
        print(f"[dfbetas] n={len(samples)}, p={p}, max|DFBETAS|={self._export_data['max_abs_dfbetas']:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
