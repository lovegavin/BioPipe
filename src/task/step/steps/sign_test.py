"""Paired sign test for exactly two equal-sized groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class SignTestStep(Step):
    name = "sign_test"
    title = "Paired sign test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        rows = []
        for i in range(len(features)):
            values = [col[:, i] for col in columns]
            rows.append(self._test(values, groups, ctx.step_params))
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"POS": 0, "NEG": 1, "P": 2},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": len(groups), "groups": groups, "method": "sign_test"}
        print(f"[sign_test] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data

    def _test(self, values, groups, params):
        if len(values) != 2:
            raise StepError("sign_test needs exactly two groups")
        if len(values[0]) != len(values[1]):
            raise StepError("sign_test requires equal paired group sizes")
        diff = values[0] - values[1]
        pos = int((diff > 0).sum())
        neg = int((diff < 0).sum())
        if pos + neg == 0:
            return [float(pos), float(neg), float("nan")]
        pvalue = stats.binomtest(
            pos, pos + neg, 0.5,
            alternative=params.get("alternative", "two-sided"),
        ).pvalue
        return [float(pos), float(neg), float(pvalue)]
