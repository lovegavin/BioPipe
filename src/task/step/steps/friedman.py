"""Friedman repeated-measures test across three or more paired groups.

All groups must have the same number of samples; pairing follows the
sample order after alignment to the metadata."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class FriedmanStep(Step):
    name = "friedman"
    title = "Friedman test"
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
                "feature_dim": {
                        "type": "string",
                        "default": "feature"
                },
                "sample_dim": {
                        "type": "string",
                        "default": "sample"
                },
                "group_dim": {
                        "type": "string",
                        "default": "sample"
                },
                "group_label": {
                        "type": "string"
                },
                "output": {
                        "type": "string"
                }
        },
        "required": [
                "group_label"
        ],
        "additionalProperties": False
}

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, group_label
        )
        if len(groups) < 3:
            raise StepError("friedman needs at least three groups")
        if len({col.shape[0] for col in columns}) != 1:
            raise StepError("friedman requires equal paired group sizes")
        rows = []
        for i in range(len(features)):
            values = [col[:, i] for col in columns]
            try:
                statistic, pvalue = stats.friedmanchisquare(*values)
            except ValueError:
                statistic, pvalue = float("nan"), float("nan")
            rows.append([float(statistic), float(pvalue)])
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"chi2": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export = {
            "n_features": len(features),
            "n_groups": len(groups),
            "groups": groups,
            "method": "friedman",
        }
        print(f"[friedman] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export
