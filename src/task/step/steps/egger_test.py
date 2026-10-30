"""Egger's regression test for small-study effects in a meta-analysis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form, table


_NAMES = [
    "intercept", "slope", "se_intercept", "se_slope",
    "t_intercept", "p_intercept", "t_slope", "p_slope", "n_studies",
]


class EggerTestStep(Step):
    name = "egger_test"
    title = "Egger's test"
    category = "Genetics"
    builtin_package = "biopipe-genetics"
    dependencies = ["numpy>=1.26", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("study_dim", "study"), param("statistic_dim", "statistic")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "study_dim": {"type": "string", "default": "study"},
            "statistic_dim": {"type": "string", "default": "statistic"},
            "effect_label": {"type": "string", "default": "effect"},
            "se_label": {"type": "string", "default": "se"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, studies, columns = table(
            inputs[0], ctx.step_params.get("study_dim", "study"),
            ctx.step_params.get("statistic_dim", "statistic"), "egger_test",
        )
        effect_label = ctx.step_params.get("effect_label", "effect")
        se_label = ctx.step_params.get("se_label", "se")
        if effect_label not in columns or se_label not in columns:
            raise StepError(
                f"egger_test: need {effect_label!r} and {se_label!r}, got {columns}"
            )
        effect = data[:, columns.index(effect_label)]
        se = data[:, columns.index(se_label)]
        mask = np.isfinite(effect) & np.isfinite(se) & (se > 0)
        effect = effect[mask]
        se = se[mask]
        if len(effect) < 3:
            raise StepError("egger_test: need at least three studies with positive SE")
        y = effect / se
        x = 1.0 / se
        design = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        residual = y - design @ beta
        df = len(y) - 2
        sigma2 = float(np.sum(residual ** 2) / df)
        cov = sigma2 * np.linalg.inv(design.T @ design)
        se_beta = np.sqrt(np.diag(cov))
        intercept, slope = float(beta[0]), float(beta[1])
        t_int = intercept / float(se_beta[0])
        t_slope = slope / float(se_beta[1])
        p_int = float(2.0 * stats.t.sf(abs(t_int), df))
        p_slope = float(2.0 * stats.t.sf(abs(t_slope), df))
        rows = [intercept, slope, float(se_beta[0]), float(se_beta[1]),
                float(t_int), p_int, float(t_slope), p_slope, len(y)]
        form = scalar_form(rows, _NAMES, "egger_test")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "intercept": intercept, "slope": slope,
            "p_intercept": p_int, "p_slope": p_slope,
            "n_studies": int(len(y)),
        }
        print(f"[egger_test] intercept={intercept:.6g} p={p_int:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
