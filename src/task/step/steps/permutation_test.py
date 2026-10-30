"""Permutation test for a difference in means between exactly two groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class PermutationTestStep(Step):
    name = "permutation_test"
    title = "Permutation test"
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
            "n_perm": {"type": "integer", "minimum": 10, "default": 1000},
            "random_state": {"type": "integer", "default": 0},
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
                "statistic": {"D": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": len(groups), "groups": groups, "method": "permutation_test"}
        print(f"[permutation_test] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data

    def _test(self, values, groups, params):
        if len(values) != 2:
            raise StepError("permutation_test needs exactly two groups")
        def delta(a, b):
            return float(np.mean(a) - np.mean(b))
        res = stats.permutation_test(
            (values[0], values[1]),
            delta,
            permutation_type="independent",
            n_resamples=int(params.get("n_perm", 1000)),
            alternative=params.get("alternative", "two-sided"),
            random_state=int(params.get("random_state", 0)),
        )
        return [float(res.statistic), float(res.pvalue)]
