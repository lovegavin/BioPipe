"""Robust scaling by median and interquartile range."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class RobustScaleStep(Step):
    name = "robust_scale"
    title = "Robust scaling"
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
            "dim": {"type": "string", "enum": ["sample", "feature"], "default": "sample"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        data = np.asarray(form.data, dtype=np.float64)
        if data.ndim != 2:
            raise StepError(f"expected a 2D form, got ndim={data.ndim}")
        dim = ctx.step_params.get("dim", "sample")
        if dim not in form.dims:
            raise StepError(f"dim {dim!r} not in {form.dims}")
        axis = form.dims.index(dim)
        med = np.nanmedian(data, axis=axis, keepdims=True)
        q1 = np.nanpercentile(data, 25, axis=axis, keepdims=True)
        q3 = np.nanpercentile(data, 75, axis=axis, keepdims=True)
        scale = q3 - q1
        scale = np.where(np.isfinite(scale) & (scale > 0), scale, 1.0)
        out = np.where(np.isfinite(data), (data - med) / scale, 0.0)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan, "transform": "robust_scale"},
        )
        self._export = {"dim": dim, "n_samples": int(data.shape[0]), "n_features": int(data.shape[1])}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
