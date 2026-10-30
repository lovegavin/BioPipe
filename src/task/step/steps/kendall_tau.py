"""Pairwise Kendall tau between two feature matrices."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form, reorder


class KendallTauStep(Step):
    name = "kendall_tau"
    title = "Kendall tau"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_x", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_y", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_x": {"type": "string", "default": "feature"},
            "feature_y": {"type": "string", "default": "feature"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        xform, yform = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        fx = ctx.step_params.get("feature_x", "feature")
        fy = ctx.step_params.get("feature_y", "feature")
        out_name = ctx.step_params.get("output", self.name)
        X = reorder(xform, sample_dim, fx).astype(np.float64)
        Y = reorder(yform, sample_dim, fy).astype(np.float64)
        xs = labels_in_order(xform, sample_dim); ys = labels_in_order(yform, sample_dim)
        if xs != ys:
            common = [s for s in xs if s in set(ys)]
            if len(common) < 3:
                raise StepError("kendall_tau needs at least three shared samples")
            X = X[[xs.index(s) for s in common]]
            Y = Y[[ys.index(s) for s in common]]
        xf = labels_in_order(xform, fx); yf = labels_in_order(yform, fy)
        tau = np.full((len(xf), len(yf)), np.nan, dtype=np.float64)
        for i in range(len(xf)):
            for j in range(len(yf)):
                mask = np.isfinite(X[:, i]) & np.isfinite(Y[:, j])
                if mask.sum() >= 3:
                    tau[i, j] = float(stats.kendalltau(X[mask, i], Y[mask, j]).statistic)
        out_fy = fy if fy != fx else f"{fy}_b"
        out = make_form(tau, [fx, out_fy],
                        {fx: {name: i for i, name in enumerate(xf)},
                         out_fy: {name: i for i, name in enumerate(yf)}})
        ctx[out_name] = out
        self._export_data = {"n_x": len(xf), "n_y": len(yf), "tau": tau.tolist()}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
