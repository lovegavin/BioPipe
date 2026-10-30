"""Two-sample Hotelling T-squared test for multivariate means."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._tests39_common import select_groups


class HotellingT2Step(Step):
    name = "hotelling_t2"
    title = "Hotelling's T-squared"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "group_a": {"type": "string"},
            "group_b": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        out_name = ctx.step_params.get("output", self.name)
        data, codes, _samples, group_a, group_b = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"], ctx.step_params["group_a"], ctx.step_params["group_b"],
            "hotelling_t2",
        )
        data = np.asarray(data, dtype=float)
        finite = np.isfinite(data).all(axis=1)
        data = data[finite]
        codes = codes[finite]
        x = data[codes == 0]
        y = data[codes == 1]
        n1, p = x.shape
        n2 = y.shape[0]
        if n1 < 2 or n2 < 2 or p < 1:
            raise StepError("hotelling_t2: need at least two samples per group and one feature")
        if n1 + n2 - p - 1 <= 0:
            raise StepError("hotelling_t2: not enough samples for the number of features")
        diff = x.mean(axis=0) - y.mean(axis=0)
        xc = x - x.mean(axis=0)
        yc = y - y.mean(axis=0)
        pooled = (xc.T @ xc + yc.T @ yc) / (n1 + n2 - 2)
        try:
            inv = np.linalg.inv(pooled)
        except np.linalg.LinAlgError as exc:
            raise StepError("hotelling_t2: pooled covariance is singular") from exc
        t2 = float((n1 * n2 / (n1 + n2)) * diff @ inv @ diff)
        f_value = float((n1 + n2 - p - 1) / (p * (n1 + n2 - 2)) * t2)
        df1 = float(p)
        df2 = float(n1 + n2 - p - 1)
        p_value = float(stats.f.sf(f_value, df1, df2))
        out = scalar_form(
            [t2, f_value, df1, df2, p_value, float(n1), float(n2), float(p)],
            ["T2", "F", "df1", "df2", "p", "n_a", "n_b", "n_features"],
            "hotelling_t2",
        )
        out.info.update({"group_a": group_a, "group_b": group_b, "test": "f"})
        ctx[out_name] = out
        self._export_data = {
            "T2": t2, "F": f_value, "df1": df1, "df2": df2, "p": p_value,
            "n_a": int(n1), "n_b": int(n2), "n_features": int(p),
            "group_a": group_a, "group_b": group_b,
        }
        print(f"[hotelling_t2] T2={t2:.6f}, F={f_value:.6f}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
