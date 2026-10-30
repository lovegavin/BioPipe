"""PCA feature loadings from a two-dimensional form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder


class PcaLoadingsStep(Step):
    name = "pca_loadings"
    title = "PCA loadings"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "n_components": {"type": "integer", "minimum": 1, "default": 10},
            "scale": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_components = int(ctx.step_params.get("n_components", 10))
        scale = bool(ctx.step_params.get("scale", True))
        out_name = ctx.step_params.get("output", self.name)
        X = reorder(form, sample_dim, feature_dim).astype(np.float64)
        if X.shape[0] < 2 or X.shape[1] < 1:
            raise StepError("pca_loadings needs at least two samples and one feature")
        col_mean = np.nanmean(X, axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
        centered = np.where(np.isfinite(X), X, col_mean) - col_mean
        if scale:
            col_std = np.nanstd(np.where(np.isfinite(X), X, np.nan), axis=0)
            col_std = np.where(np.isfinite(col_std) & (col_std > 1e-12), col_std, 1.0)
            centered = centered / col_std
        k = min(n_components, min(centered.shape))
        _, s, vt = np.linalg.svd(centered, full_matrices=False)
        loadings = vt[:k].T.astype(np.float32)
        features = labels_in_order(form, feature_dim)
        out = Form(
            data=loadings,
            dims=[feature_dim, "component"],
            labels={feature_dim: {name: i for i, name in enumerate(features)},
                    "component": {f"PC{i + 1}": i for i in range(k)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        explained = (s[:k] ** 2) / float((s ** 2).sum())
        self._export_data = {"n_components": k, "scale": scale,
                             "explained_variance_ratio": [float(v) for v in explained],
                             "features": features}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
