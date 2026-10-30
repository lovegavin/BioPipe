"""Rank transform each feature, optionally to normal scores."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class RankTransformStep(Step):
    name = "rank_transform"
    title = "Rank transform"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy"]
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
            "method": {"type": "string", "enum": ["average", "min", "max", "dense", "ordinal"], "default": "average"},
            "normal_score": {"type": "boolean", "default": False},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        x, samples, features = matrix(form, ctx.step_params.get("sample_dim", "sample"), ctx.step_params.get("feature_dim", "feature"))
        method = ctx.step_params.get("method", "average")
        normal_score = bool(ctx.step_params.get("normal_score", False))
        out = np.full_like(x, np.nan)
        for j in range(x.shape[1]):
            col = x[:, j]
            finite = np.isfinite(col)
            n = int(finite.sum())
            if n == 0:
                continue
            ranks = stats.rankdata(col[finite], method=method)
            if normal_score:
                ranks = stats.norm.ppf((ranks - 0.5) / n)
            out[finite, j] = ranks
        axis = form.dims.index(ctx.step_params.get("sample_dim", "sample"))
        data = np.moveaxis(out, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "rank", "method": method, "normal_score": normal_score},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "method": method, "normal_score": normal_score}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
