"""Benjamini-Hochberg false-discovery-rate adjustment."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class BhAdjustStep(Step):
    name = "bh_adjust"
    title = "Benjamini-Hochberg FDR"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("feature_dim", "feature"), param("value_dim", "statistic")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "value_dim": {"type": "string", "default": "pvalue"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_dim = ctx.step_params.get("value_dim", "pvalue")
        if form.data.ndim != 2:
            raise StepError("bh_adjust expects a 2D form")
        if feature_dim not in form.dims or value_dim not in form.dims:
            raise StepError(f"bh_adjust: expected {feature_dim!r} and {value_dim!r} in {form.dims}")
        axis = form.dims.index(value_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, 1)
        if values.shape[1] != 1:
            raise StepError("bh_adjust expects exactly one value column")
        p = values[:, 0]
        if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
            raise StepError("bh_adjust: p-values must be finite and in [0, 1]")
        order = np.argsort(p)
        ranked = p[order]
        n = len(p)
        q = np.empty(n, dtype=np.float64)
        running = 1.0
        for rank in range(n, 0, -1):
            running = min(running, ranked[rank - 1] * n / rank)
            q[rank - 1] = running
        q_out = np.empty(n, dtype=np.float64)
        q_out[order] = np.clip(q, 0.0, 1.0)
        feature_labels = form.labels[feature_dim]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=q_out.reshape(-1, 1).astype(np.float32),
            dims=[feature_dim, "statistic"],
            labels={feature_dim: dict(feature_labels), "statistic": {"qvalue": 0}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_tests": n, "n_significant_0_05": int((q_out < 0.05).sum())}
        print(f"[bh_adjust] {n} tests, {(q_out < 0.05).sum()} at q<0.05")

    def export(self, ctx: Context) -> dict:
        return self._export_data
