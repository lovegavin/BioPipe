"""Cochran's Q test for paired binary outcomes across conditions."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import table_frame


class CochranQStep(Step):
    """Test equality of binary responses across three or more conditions."""

    name = "cochran_q"
    title = "Cochran's Q test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": False,
            "axis_info_open": False,
            "info": {"missing_code": {"type": ["number", "null"]}},
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "conditions": {"type": "array", "items": {"type": "string"}},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "cochran_q")
        conditions = list(ctx.step_params.get("conditions") or [])
        if not conditions:
            conditions = [name for name in frame.columns if name != "__sample__"]
        conditions = [str(name) for name in conditions]
        if len(conditions) < 2:
            raise StepError("cochran_q: at least two condition columns are required")
        missing = [name for name in conditions if name not in frame.columns]
        if missing:
            raise StepError(f"cochran_q: condition columns not found: {missing}")
        data = frame[conditions].to_numpy(dtype=np.float64)
        keep = np.all(np.isfinite(data), axis=1)
        data = data[keep]
        if data.shape[0] < 2:
            raise StepError("cochran_q: fewer than two complete subjects")
        if not np.all((data == 0.0) | (data == 1.0)):
            raise StepError("cochran_q: condition columns must contain only 0/1")
        n, k = data.shape
        column_sums = data.sum(axis=0)
        row_sums = data.sum(axis=1)
        denominator = float(k * row_sums.sum() - np.square(row_sums).sum())
        if denominator <= 0:
            raise StepError("cochran_q: responses do not vary across subjects")
        numerator = float(
            (k - 1) * (k * np.square(column_sums).sum() - column_sums.sum() ** 2)
        )
        statistic = numerator / denominator
        df = k - 1
        p_value = float(stats.chi2.sf(statistic, df))
        out = make_form(
            [
                [statistic],
                [float(df)],
                [p_value],
                [float(n)],
                [float(k)],
            ],
            ["statistic", "value"],
            {
                "statistic": {
                    "statistic": 0,
                    "df": 1,
                    "p": 2,
                    "n": 3,
                    "n_conditions": 4,
                },
                "value": {"value": 0},
            },
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic,
            "df": int(df),
            "p": p_value,
            "n": int(n),
            "n_conditions": int(k),
            "conditions": conditions,
        }
        print(f"[cochran_q] Q={statistic:.4f}, df={df}, p={p_value:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
