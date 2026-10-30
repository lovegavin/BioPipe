"""One-sample Student t-test against a fixed population mean."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class TTestOneSampleStep(Step):
    name = "ttest_one_sample"
    title = "One-sample t-test"
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
            "popmean": {"type": "number", "default": 0.0},
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, _samples, features = matrix(form, sample_dim, feature_dim)
        popmean = float(ctx.step_params.get("popmean", 0.0))
        alternative = ctx.step_params.get("alternative", "two-sided")
        from scipy import stats

        rows = []
        for i in range(len(features)):
            try:
                statistic, pvalue = stats.ttest_1samp(X[:, i], popmean, alternative=alternative, nan_policy="omit")
            except ValueError:
                statistic, pvalue = float("nan"), float("nan")
            rows.append([float(statistic), float(pvalue)])
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"T": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export = {"n_features": len(features), "popmean": popmean, "method": "one_sample_t_test"}
        print(f"[ttest_one_sample] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export
