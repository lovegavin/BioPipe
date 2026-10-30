"""Storey q-values with a fixed lambda estimate of pi0."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class StoreyQvalueStep(Step):
    """Storey's q-value procedure for a column of p-values."""

    name = "storey_qvalue"
    title = "Storey q-values"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("feature_dim", "feature"), param("value_dim", "statistic")],
        )
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "value_dim": {"type": "string", "default": "pvalue"},
            "lambda": {
                "type": "number",
                "minimum": 0.05,
                "maximum": 0.95,
                "default": 0.5,
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_dim = ctx.step_params.get("value_dim", "pvalue")
        if form.data.ndim != 2:
            raise StepError("storey_qvalue expects a 2D form")
        if feature_dim not in form.dims or value_dim not in form.dims:
            raise StepError(
                f"storey_qvalue: expected {feature_dim!r} and {value_dim!r} "
                f"in {form.dims}"
            )
        axis = form.dims.index(value_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, 1)
        if values.shape[1] != 1:
            raise StepError("storey_qvalue expects exactly one p-value column")
        p = values[:, 0]
        if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
            raise StepError("storey_qvalue: p-values must be finite and in [0, 1]")

        lam = float(ctx.step_params.get("lambda", 0.5))
        if not 0.0 <= lam < 1.0:
            raise StepError("storey_qvalue: lambda must be in [0, 1)")
        n = len(p)
        if n == 0:
            raise StepError("storey_qvalue: no p-values")

        pi0 = float(np.mean(p >= lam) / (1.0 - lam)) if lam < 1.0 else 1.0
        pi0 = float(np.clip(pi0, 0.0, 1.0))
        order = np.argsort(p, kind="mergesort")
        ranked = p[order]
        q = np.empty(n, dtype=np.float64)
        running = 1.0
        for rank in range(n, 0, -1):
            running = min(running, pi0 * n * ranked[rank - 1] / rank)
            q[rank - 1] = running
        q_out = np.empty(n, dtype=np.float64)
        q_out[order] = np.clip(q, 0.0, 1.0)

        feature_labels = form.labels[feature_dim]
        out = Form(
            data=q_out.reshape(-1, 1).astype(np.float32),
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: dict(feature_labels),
                "statistic": {"qvalue": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "storey_fixed_lambda",
                "lambda": lam,
                "pi0": pi0,
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export_data = {
            "n_tests": n,
            "pi0": pi0,
            "lambda": lam,
            "n_q_lt_0_05": int((q_out < 0.05).sum()),
        }
        print(f"[storey_qvalue] n={n}, pi0={pi0:.3f}, q<0.05={int((q_out < 0.05).sum())}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
