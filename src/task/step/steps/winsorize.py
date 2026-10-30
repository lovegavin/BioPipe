"""Winsorise each feature at lower and upper percentiles."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class WinsorizeStep(Step):
    name = "winsorize"
    title = "Winsorise"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
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
            "lower": {"type": "number", "minimum": 0, "maximum": 100, "default": 5.0},
            "upper": {"type": "number", "minimum": 0, "maximum": 100, "default": 95.0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        lower = float(ctx.step_params.get("lower", 5.0))
        upper = float(ctx.step_params.get("upper", 95.0))
        if not 0 <= lower < upper <= 100:
            raise StepError("winsorize requires 0 <= lower < upper <= 100")
        x, samples, features = matrix(form, ctx.step_params.get("sample_dim", "sample"), ctx.step_params.get("feature_dim", "feature"))
        lo = np.nanpercentile(x, lower, axis=0)
        hi = np.nanpercentile(x, upper, axis=0)
        out = np.clip(x, lo, hi)
        axis = form.dims.index(ctx.step_params.get("sample_dim", "sample"))
        data = np.moveaxis(out, 0, axis)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "winsorize", "lower": lower, "upper": upper},
        )
        self._export = {"n_samples": int(x.shape[0]), "n_features": int(x.shape[1]), "lower": lower, "upper": upper}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
