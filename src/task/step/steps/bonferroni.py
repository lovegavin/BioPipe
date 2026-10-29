"""Bonferroni multiple-testing correction.

Reads a feature x statistic table with one p-value column and writes
a feature x statistic table containing only qvalues. Bonferroni qvalues
are min(p * m, 1), where m is the number of finite p-values.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class BonferroniStep(Step):
    name = "bonferroni"
    title = "Bonferroni correction"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("feature_dim", "feature"), param("statistic", "statistic")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "statistic_dim": {"type": "string", "default": "statistic"},
            "value_dim": {"type": "string", "default": "pvalue"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        statistic_dim = ctx.step_params.get("statistic_dim", "statistic")
        value_dim = ctx.step_params.get("value_dim", "pvalue")
        if feature_dim not in form.dims or statistic_dim not in form.dims:
            raise StepError(f"bonferroni: expected dims {feature_dim!r} and {statistic_dim!r}, got {form.dims}")
        labels = form.labels[statistic_dim]
        if value_dim not in labels:
            raise StepError(f"bonferroni: value dimension {value_dim!r} is not in {sorted(labels)}")
        axis = form.dims.index(statistic_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, -1)
        pvalues = values[..., labels[value_dim]]
        if np.any(~np.isfinite(pvalues)):
            raise StepError("bonferroni: p-values must be finite")
        if np.any((pvalues < 0.0) | (pvalues > 1.0)):
            raise StepError("bonferroni: p-values must be between 0 and 1")
        m = int(pvalues.size)
        qvalues = np.minimum(pvalues * m, 1.0)
        data = qvalues.reshape(-1, 1)
        fdim = form.dims[0] if form.dims[0] != statistic_dim else form.dims[1]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=[fdim, statistic_dim],
            labels={
                fdim: dict(form.labels[fdim]),
                statistic_dim: {"qvalue": 0},
            },
            info={"missing_code": np.nan, "correction": "bonferroni", "n_tests": m},
        )
        self._export = {"n_tests": m, "method": "bonferroni"}
        print(f"[bonferroni] {m} tests")

    def export(self, ctx: Context) -> dict:
        return self._export
