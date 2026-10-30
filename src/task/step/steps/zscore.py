"""Per-feature or per-sample z-score standardisation.

NaNs are replaced with the axis mean and constant axes are left unchanged."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class ZscoreStep(Step):
    name = "zscore"
    title = "Z-score scaling"
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
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        if sample_dim not in form.dims or feature_dim not in form.dims:
            raise StepError(f"expected dims {sample_dim!r} and {feature_dim!r}, got {form.dims}")
        dim = ctx.step_params.get("dim", "feature")
        if dim not in form.dims:
            raise StepError(f"dim {dim!r} not in {form.dims}")
        axis = form.dims.index(dim)
        if data.shape[axis] < 2:
            raise StepError(f"{self.name} needs at least two entries along {dim!r}")
        out = self._transform(data, axis, ctx.step_params)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=list(form.dims),
            labels={name: dict(values) for name, values in form.labels.items()},
            info={"missing_code": np.nan},
        )
        self._export = {"dim": dim, "n_samples": int(data.shape[0]), "n_features": int(data.shape[1])}
        print(f"[{self.name}] scaled along {dim}")

    def export(self, ctx: Context) -> dict:
        return self._export

    def _transform(self, data, axis, params):
        mean = np.nanmean(data, axis=axis, keepdims=True)
        std = np.nanstd(data, axis=axis, ddof=1, keepdims=True)
        std = np.where(np.isfinite(std) & (std > 0), std, 1.0)
        return np.where(np.isfinite(data), (data - mean) / std, 0.0)
