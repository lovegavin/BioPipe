"""D'Agostino-Pearson normality test per feature.

Computes scipy.stats.normaltest independently for each feature. At
least eight samples are required by the test. Missing values are
mean-imputed by the shared matrix helper.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class NormaltestStep(Step):
    name = "normaltest"
    title = "D'Agostino-Pearson normality test"
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
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        X, _samples, features = matrix(inputs[0], sample_dim, feature_dim)
        if X.shape[0] < 8:
            raise StepError("normaltest needs at least eight samples")
        rows = []
        for i in range(X.shape[1]):
            try:
                statistic, pvalue = stats.normaltest(X[:, i])
            except ValueError:
                statistic, pvalue = float("nan"), float("nan")
            rows.append([float(statistic), float(pvalue)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"K2": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export = {"n_features": len(features), "n_samples": int(X.shape[0]), "method": "normaltest"}
        print(f"[normaltest] {len(features)} features, {X.shape[0]} samples")

    def export(self, ctx: Context) -> dict:
        return self._export
