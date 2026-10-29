"""Shapiro-Wilk normality test for every feature."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class ShapiroStep(Step):
    name = "shapiro"
    title = "Shapiro-Wilk test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
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
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, _samples, features = matrix(form, sample_dim, feature_dim)
        if X.shape[0] < 3:
            raise StepError("shapiro needs at least three samples per feature")
        rows = []
        for i in range(len(features)):
            w, p = stats.shapiro(X[:, i])
            rows.append([float(w), float(p)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)}, "statistic": {"W": 0, "P": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_samples": int(X.shape[0])}
        print(f"[shapiro] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
