"""Bland-Altman agreement summary for two measurement columns."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class BlandAltmanStep(Step):
    name = "bland_altman"
    title = "Bland-Altman agreement"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "method_a": {"type": "string"},
            "method_b": {"type": "string"},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "required": ["method_a", "method_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        a_name = ctx.step_params["method_a"]
        b_name = ctx.step_params["method_b"]
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if form.data.ndim != 2:
            raise StepError("bland_altman: input must be 2D")
        for dim in (sample_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(f"bland_altman: dim {dim!r} not in {form.dims}")
        if not (0 < confidence < 1):
            raise StepError("bland_altman: confidence must be in (0, 1)")
        if a_name == b_name:
            raise StepError("bland_altman: method_a and method_b must differ")
        labels = form.labels.get(feature_dim, {})
        for name in (a_name, b_name):
            if name not in labels:
                raise StepError(f"bland_altman: column {name!r} not found")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(sample_dim) == 1:
            data = data.T
        a = data[:, labels[a_name]]
        b = data[:, labels[b_name]]
        keep = np.isfinite(a) & np.isfinite(b)
        a, b = a[keep], b[keep]
        n = a.size
        if n < 2:
            raise StepError("bland_altman: need at least two complete pairs")
        diff = a - b
        mean_diff = float(np.mean(diff))
        sd_diff = float(np.std(diff, ddof=1))
        se_mean = sd_diff / np.sqrt(n)
        tcrit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, n - 1))
        ci_low = mean_diff - tcrit * se_mean
        ci_high = mean_diff + tcrit * se_mean
        loa_low = mean_diff - 1.96 * sd_diff
        loa_high = mean_diff + 1.96 * sd_diff
        values = [
            ("mean_a", float(np.mean(a))), ("mean_b", float(np.mean(b))),
            ("mean_diff", mean_diff), ("sd_diff", sd_diff),
            ("ci_low", ci_low), ("ci_high", ci_high),
            ("loa_low", loa_low), ("loa_high", loa_high),
            ("n", float(n)),
        ]
        out = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {"statistic": {name: i for i, (name, _) in enumerate(values)},
             "value": {"value": 0}},
        )
        ctx[out_name] = out
        self._export_data = {
            "mean_a": float(np.mean(a)), "mean_b": float(np.mean(b)),
            "mean_diff": mean_diff, "sd_diff": sd_diff,
            "ci_low": ci_low, "ci_high": ci_high,
            "loa_low": loa_low, "loa_high": loa_high,
            "n": int(n), "confidence": confidence,
        }
        print(
            f"[bland_altman] n={n} mean_diff={mean_diff:.4g} "
            f"LoA=[{loa_low:.4g}, {loa_high:.4g}]"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
