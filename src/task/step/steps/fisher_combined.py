"""Fisher's combined probability test per feature.

Combines two or more p-value columns per feature using
scipy.stats.combine_pvalues(method="fisher"). Input layout is
feature x statistic with p-value columns labelled pvalue, pvalue1,
pvalue2, ...; output is feature x statistic with chi2 and P.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class FisherCombinedStep(Step):
    name = "fisher_combined"
    title = "Fisher combined p-value"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("feature_dim", "feature"), param("statistic_dim", "statistic")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "statistic_dim": {"type": "string", "default": "statistic"},
            "pvalue_dims": {"type": "array", "items": {"type": "string"}, "default": []},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        statistic_dim = ctx.step_params.get("statistic_dim", "statistic")
        if feature_dim not in form.dims or statistic_dim not in form.dims:
            raise StepError(f"fisher_combined: expected dims {feature_dim!r} and {statistic_dim!r}, got {form.dims}")
        labels = form.labels[statistic_dim]
        ordered = [name for name, _ in sorted(labels.items(), key=lambda kv: kv[1])]
        requested = list(ctx.step_params.get("pvalue_dims") or [])
        if requested:
            missing = [name for name in requested if name not in labels]
            if missing:
                raise StepError(f"fisher_combined: p-value columns not found: {missing}")
            columns = requested
        else:
            columns = [name for name in ordered if "pvalue" in name.lower()]
            if not columns:
                raise StepError(
                    "fisher_combined: no p-value column found; pass pvalue_dims explicitly"
                )
        axis = form.dims.index(statistic_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, 1)
        pick = [labels[name] for name in columns]
        pvalues = values[:, pick]
        if pvalues.ndim != 2 or pvalues.shape[1] < 1:
            raise StepError("fisher_combined: expected a feature x p-value matrix")
        if np.any(~np.isfinite(pvalues)) or np.any((pvalues < 0.0) | (pvalues > 1.0)):
            raise StepError("fisher_combined: p-values must be finite and between 0 and 1")
        rows = []
        for i in range(pvalues.shape[0]):
            statistic, pvalue = stats.combine_pvalues(pvalues[i], method="fisher")
            rows.append([float(statistic), float(pvalue)])
        fdim = form.dims[0] if form.dims[0] != statistic_dim else form.dims[1]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[fdim, statistic_dim],
            labels={
                fdim: dict(form.labels[fdim]),
                statistic_dim: {"chi2": 0, "P": 1},
            },
            info={"missing_code": np.nan, "method": "fisher"},
        )
        self._export = {
            "n_features": int(pvalues.shape[0]),
            "n_pvalues": int(pvalues.shape[1]),
            "method": "fisher",
        }
        print(f"[fisher_combined] {pvalues.shape[0]} features, {pvalues.shape[1]} p-values")

    def export(self, ctx: Context) -> dict:
        return self._export
