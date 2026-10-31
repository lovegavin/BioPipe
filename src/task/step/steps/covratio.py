"""COVRATIO influence statistic for an ordinary least-squares fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class CovratioStep(Step):
    name = "covratio"
    title = "COVRATIO"
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
            inputs[0], sample_dim, feature_dim, response, "covratio"
        )
        n = design.shape[0]
        sigma_i = np.sqrt(s2_i)
        e_star = residuals / (sigma_i * np.sqrt(1.0 - leverage))
        denominator = (1.0 - leverage) * (((n - p - 1) + e_star * e_star) / (n - p)) ** p
        ratio = 1.0 / denominator
        form = Form(
            data=np.asarray(ratio, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={"sample": {name: i for i, name in enumerate(samples)}, "metric": {"covratio": 0}},
            info={
                "missing_code": np.nan,
                "response": response,
                "predictors": predictors,
                "p": int(p),
                "n": int(n),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n": int(n),
            "p": int(p),
            "response": response,
            "predictors": predictors,
            "min_covratio": float(np.min(ratio)),
            "max_covratio": float(np.max(ratio)),
            "min_sample": samples[int(np.argmin(ratio))],
            "max_sample": samples[int(np.argmax(ratio))],
        }
        print(f"[covratio] n={n}, p={p}, range={np.min(ratio):.4g}..{np.max(ratio):.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
