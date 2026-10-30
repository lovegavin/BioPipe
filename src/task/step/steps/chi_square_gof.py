"""Pearson chi-square goodness-of-fit test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ChiSquareGofStep(Step):
    """One-sample chi-square test against expected relative frequencies."""

    name = "chi_square_gof"
    title = "Pearson chi-square goodness-of-fit test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("category_dim", "category"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "category_dim": {"type": "string", "default": "category"},
            "feature_dim": {"type": "string", "default": "feature"},
            "count_label": {"type": "string", "title": "计数列"},
            "expected": {
                "type": "array",
                "items": {"type": "number"},
                "default": [],
                "title": "期望相对频数（留空为均匀分布）",
            },
            "output": {"type": "string"},
        },
        "required": ["count_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        category_dim = ctx.step_params.get("category_dim", "category")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        count_label = ctx.step_params["count_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, category_dim, feature_dim, self.name)
        counts = numeric_column(frame, count_label, self.name)
        if counts.size < 2:
            raise StepError("chi_square_gof: at least two categories are required")
        if not np.isfinite(counts).all() or np.any(counts < 0):
            raise StepError("chi_square_gof: counts must be finite and nonnegative")
        total = float(counts.sum())
        if total <= 0:
            raise StepError("chi_square_gof: total count must be positive")
        expected = np.asarray(ctx.step_params.get("expected") or [], dtype=np.float64)
        rescaled = False
        if expected.size:
            if expected.size != counts.size:
                raise StepError("chi_square_gof: expected must match the number of categories")
            if not np.isfinite(expected).all() or np.any(expected <= 0):
                raise StepError("chi_square_gof: expected values must be finite and positive")
            weights = expected / expected.sum()
            expected = weights * total
            rescaled = True
        else:
            expected = np.full(counts.size, total / counts.size)
        result = stats.chisquare(counts, f_exp=expected)
        statistic = float(result.statistic)
        p_value = float(result.pvalue)
        df = counts.size - 1
        out = scalar_form(
            [statistic, float(df), p_value, float(counts.size), total],
            ["statistic", "df", "p", "n_categories", "n"],
            self.name,
        )
        out.info.update(
            {
                "expected": "uniform" if not rescaled else "user",
                "expected_rescaled": rescaled,
                "categories": [str(value) for value in frame["__sample__"]],
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic,
            "df": int(df),
            "p": p_value,
            "n_categories": int(counts.size),
            "n": total,
            "expected_rescaled": rescaled,
        }
        print(f"[{self.name}] chi2={statistic:.6f}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
