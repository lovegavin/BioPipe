"""Boschloo's exact unconditional test for a 2x2 table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form


class BoschlooExactStep(Step):
    """Boschloo's exact test for association in a 2x2 contingency table.

    Boschloo's p-value is the maximum conditional Fisher p-value over tables
    with the same margins; it is uniformly more powerful than Fisher's exact
    test. The odds ratio is the sample odds ratio.
    """

    name = "boschloo_exact"
    title = "Boschloo exact test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("row_dim", "row"), param("column_dim", "column")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "row"},
            "column_dim": {"type": "string", "default": "column"},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "greater", "less"],
                "default": "two-sided",
                "title": "备择假设",
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)

        if row_dim not in form.dims or column_dim not in form.dims:
            raise StepError(f"boschloo_exact: expected dims {row_dim!r}, {column_dim!r}")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(row_dim) == 1:
            data = data.T
        if data.shape != (2, 2):
            raise StepError("boschloo_exact: input must be a 2x2 table")
        if not np.all(np.isfinite(data)):
            raise StepError("boschloo_exact: table cells must be finite")
        rounded = np.rint(data)
        if np.max(np.abs(data - rounded)) > 1e-9:
            raise StepError("boschloo_exact: table cells must be integer counts")
        if np.any(rounded < 0):
            raise StepError("boschloo_exact: table cells must be non-negative")
        table = rounded.astype(np.int64)
        if np.any(table.sum(axis=0) == 0) or np.any(table.sum(axis=1) == 0):
            raise StepError("boschloo_exact: every row and column needs a non-zero margin")

        try:
            result = stats.boschloo_exact(table, alternative=alternative)
            fisher = stats.fisher_exact(table, alternative=alternative)
        except ValueError as exc:
            raise StepError(f"boschloo_exact: {exc}") from exc
        p_value = float(result.pvalue)
        fisher_p = float(result.statistic)
        odds_ratio = float(fisher.statistic)
        n = int(table.sum())
        out = scalar_form(
            [p_value, fisher_p, odds_ratio, float(n)],
            ["p", "fisher_p", "odds_ratio", "n"],
            "boschloo_exact",
        )
        out.info.update({"alternative": alternative, "method": "Boschloo exact unconditional"})
        ctx[out_name] = out
        self._export_data = {
            "p": p_value, "fisher_p": fisher_p, "odds_ratio": odds_ratio,
            "n": n, "alternative": alternative,
        }
        print(f"[boschloo_exact] p={p_value:.6g}, fisher_p={fisher_p:.6g}, OR={odds_ratio:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
