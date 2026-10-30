"""Highly variable gene ranking by mean/variance dispersion."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import matrix


class HvgStep(Step):
    name = "hvg"
    title = "Highly variable genes"
    category = "Single cell"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "gene")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "gene"},
            "n_top": {"type": "integer", "minimum": 1, "default": 2000},
            "min_mean": {"type": "number", "default": -1e12},
            "max_mean": {"type": "number", "minimum": 0, "default": 1e12},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "gene")
        n_top = int(ctx.step_params.get("n_top", 2000))
        min_mean = float(ctx.step_params.get("min_mean", -1e12))
        max_mean = float(ctx.step_params.get("max_mean", 1e12))
        out_name = ctx.step_params.get("output", self.name)
        X, _, features = matrix(form, sample_dim, feature_dim)
        mean = X.mean(axis=0)
        var = X.var(axis=0, ddof=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            dispersion = var / mean
        dispersion = np.where(np.isfinite(dispersion), dispersion, 0.0)
        eligible = (mean >= min_mean) & (mean <= max_mean)
        order = np.argsort(-dispersion, kind="mergesort")
        selected = order[eligible[order]][:n_top]
        hv = np.zeros(len(features), dtype=np.float32)
        hv[selected] = 1.0
        data = np.column_stack([mean, var, dispersion, hv]).astype(np.float32)
        out = Form(
            data=data,
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)},
                    "statistic": {"mean": 0, "variance": 1, "dispersion": 2, "highly_variable": 3}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_features": len(features), "n_selected": int(hv.sum()),
                             "n_top": n_top, "min_mean": min_mean, "max_mean": max_mean,
                             "selected": [features[i] for i in selected]}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
