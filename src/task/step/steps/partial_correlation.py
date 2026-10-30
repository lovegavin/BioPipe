"""Partial Pearson correlation after residualising both sides on covariates."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class PartialCorrelationStep(Step):
    name = "partial_correlation"
    title = "Partial correlation"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 3
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("x_feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("y_feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("covariate_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "x_feature_dim": {"type": "string", "default": "feature"},
            "y_feature_dim": {"type": "string", "default": "feature"},
            "covariate_dim": {"type": "string", "default": "feature"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        x, xs, xf = matrix(inputs[0], sample_dim, ctx.step_params.get("x_feature_dim", "feature"))
        y, ys, yf = matrix(inputs[1], sample_dim, ctx.step_params.get("y_feature_dim", "feature"))
        c, cs, cf = matrix(inputs[2], sample_dim, ctx.step_params.get("covariate_dim", "feature"))
        if x.shape[1] != y.shape[1]:
            raise StepError(f"x and y need the same number of features, got {x.shape[1]} and {y.shape[1]}")
        if c.shape[1] == 0:
            raise StepError("at least one covariate is required")
        xpos = {name: i for i, name in enumerate(xs)}
        ypos = {name: i for i, name in enumerate(ys)}
        cpos = {name: i for i, name in enumerate(cs)}
        shared = [name for name in xs if name in ypos and name in cpos]
        if len(shared) <= c.shape[1] + 2:
            raise StepError(f"not enough shared samples ({len(shared)}) for {c.shape[1]} covariates")
        x = x[[xpos[name] for name in shared]]
        y = y[[ypos[name] for name in shared]]
        c = c[[cpos[name] for name in shared]]
        design = np.column_stack([np.ones(len(shared)), c])
        out = np.full((x.shape[1], 4), np.nan, dtype=np.float64)
        for j in range(x.shape[1]):
            rx = x[:, j] - design @ np.linalg.lstsq(design, x[:, j], rcond=None)[0]
            ry = y[:, j] - design @ np.linalg.lstsq(design, y[:, j], rcond=None)[0]
            if np.std(rx) == 0 or np.std(ry) == 0:
                continue
            r = float(np.corrcoef(rx, ry)[0, 1])
            df = len(shared) - c.shape[1] - 2
            if df <= 0 or abs(r) >= 1:
                t = float("inf") if abs(r) >= 1 else 0.0
                p = 0.0
            else:
                t = r * np.sqrt(df / (1.0 - r * r))
                p = 2.0 * stats.t.sf(abs(t), df)
            out[j] = (r, t, p, df)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(xf)},
                "statistic": {"r": 0, "t": 1, "p": 2, "df": 3},
            },
            info={"missing_code": np.nan, "method": "partial_pearson"},
        )
        self._export = {"n_samples": len(shared), "n_features": int(x.shape[1]), "n_covariates": int(c.shape[1])}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
