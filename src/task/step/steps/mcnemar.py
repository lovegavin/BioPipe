"""McNemar test for paired binary labels."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class McnemarStep(Step):
    name = "mcnemar"
    title = "McNemar test"
    category = "Statistics"
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
            "label_a": {"type": "string"},
            "label_b": {"type": "string"},
            "exact": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "required": ["label_a", "label_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        a_name = ctx.step_params["label_a"]; b_name = ctx.step_params["label_b"]
        exact = bool(ctx.step_params.get("exact", True))
        out_name = ctx.step_params.get("output", self.name)
        for name in (a_name, b_name):
            if name not in form.labels.get(feature_dim, {}):
                raise StepError(f"mcnemar: column {name!r} not found")
        data = np.moveaxis(np.asarray(form.data), form.dims.index(sample_dim), 0)
        a = data[:, form.labels[feature_dim][a_name]]
        b = data[:, form.labels[feature_dim][b_name]]
        keep = np.isfinite(a) & np.isfinite(b)
        a, b = (a[keep] > 0), (b[keep] > 0)
        b01 = int(np.sum((~a) & b))
        b10 = int(np.sum(a & (~b)))
        n = b01 + b10
        if n == 0:
            stat, p = 0.0, 1.0
        elif exact:
            stat = float(min(b01, b10))
            p = float(stats.binomtest(min(b01, b10), n, 0.5).pvalue)
        else:
            stat = float((abs(b01 - b10) - 1.0) ** 2 / n)
            p = float(stats.chi2.sf(stat, 1))
        out = make_form([[b01], [b10], [stat], [p]], ["statistic", "value"],
                        {"statistic": {"b01": 0, "b10": 1, "statistic": 2, "p": 3}, "value": {"value": 0}})
        ctx[out_name] = out
        self._export_data = {"b01": b01, "b10": b10, "statistic": stat, "p": p, "exact": exact}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
