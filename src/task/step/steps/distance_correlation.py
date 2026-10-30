"""Pairwise distance correlation between two feature matrices.

Distance correlation is zero exactly when two random vectors are independent
(in the population sense), unlike Pearson correlation which only measures
linear association.  The statistic is computed from double-centred Euclidean
distance matrices.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


def _dcor(u: np.ndarray, v: np.ndarray) -> float:
    a = np.abs(u[:, None] - u[None, :]).astype(np.float64)
    b = np.abs(v[:, None] - v[None, :]).astype(np.float64)
    a -= a.mean(axis=0, keepdims=True)
    a -= a.mean(axis=1, keepdims=True)
    a += a.mean()
    b -= b.mean(axis=0, keepdims=True)
    b -= b.mean(axis=1, keepdims=True)
    b += b.mean()
    cov = float((a * b).mean())
    var_x = float((a * a).mean())
    var_y = float((b * b).mean())
    denom = np.sqrt(max(var_x, 0.0) * max(var_y, 0.0))
    if denom <= 0:
        return float("nan")
    return float(np.sqrt(max(cov, 0.0) / denom))


class DistanceCorrelationStep(Step):
    name = "distance_correlation"
    title = "Distance correlation"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("x_feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("y_feature_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "x_feature_dim": {"type": "string", "default": "feature"},
            "y_feature_dim": {"type": "string", "default": "feature"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        x, xs, xf = matrix(inputs[0], sample_dim, ctx.step_params.get("x_feature_dim", "feature"))
        y, ys, yf = matrix(inputs[1], sample_dim, ctx.step_params.get("y_feature_dim", "feature"))
        xpos = {name: i for i, name in enumerate(xs)}
        ypos = {name: i for i, name in enumerate(ys)}
        shared = [name for name in ys if name in xpos]
        if len(shared) < 4:
            raise StepError(f"only {len(shared)} shared samples between inputs")
        x = x[[xpos[name] for name in shared]]
        y = y[[ypos[name] for name in shared]]
        out = np.empty((x.shape[1], y.shape[1]), dtype=np.float64)
        for i in range(x.shape[1]):
            for j in range(y.shape[1]):
                out[i, j] = _dcor(x[:, i], y[:, j])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=["x_feature", "y_feature"],
            labels={
                "x_feature": {name: i for i, name in enumerate(xf)},
                "y_feature": {name: i for i, name in enumerate(yf)},
            },
            info={"missing_code": np.nan, "method": "distance_correlation"},
        )
        self._export = {"n_samples": len(shared), "n_x_features": int(x.shape[1]), "n_y_features": int(y.shape[1])}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
