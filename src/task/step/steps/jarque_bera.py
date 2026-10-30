"""Jarque-Bera normality test for every feature."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class JarqueBeraStep(Step):
    name = "jarque_bera"
    title = "Jarque-Bera normality test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        X, samples, features = matrix(data, sample_dim, feature_dim)
        rows = []
        for i in range(len(features)):
            res = stats.jarque_bera(X[:, i])
            rows.append([float(res.statistic), float(res.pvalue)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"JB": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "method": "jarque_bera"}
        print(f"[jarque_bera] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
