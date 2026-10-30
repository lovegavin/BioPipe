"""Bhapkar test for marginal homogeneity in a square table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form


class BhapkarTestStep(Step):
    """Bhapkar test, the Stuart-Maxwell statistic with a finite-sample correction."""

    name = "bhapkar_test"
    title = "Bhapkar test"
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
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        out_name = ctx.step_params.get("output", self.name)
        data = np.asarray(form.data, dtype=np.float64)
        if data.ndim != 2 or data.shape[0] != data.shape[1] or data.shape[0] < 2:
            raise StepError("bhapkar_test: expected a square table with at least two categories")
        if not np.all(np.isfinite(data)) or np.any(data < 0):
            raise StepError("bhapkar_test: counts must be finite and non-negative")
        total = float(data.sum())
        if total <= 0:
            raise StepError("bhapkar_test: table must not be empty")
        row = data.sum(axis=1)
        col = data.sum(axis=0)
        # Match DescTools::BhapkarTest / StuartMaxwellTest: drop categories
        # whose diagonal equals both margins before building the covariance.
        keep = ~((np.diag(data) == row) & (np.diag(data) == col))
        table = data[np.ix_(keep, keep)]
        r = table.shape[0]
        if r < 2:
            raise StepError("bhapkar_test: too many equal marginals")
        row = table.sum(axis=1)
        col = table.sum(axis=0)
        delta = (row - col)[: r - 1]
        covariance = np.zeros((r - 1, r - 1), dtype=np.float64)
        for i in range(r - 1):
            for j in range(r - 1):
                if i == j:
                    covariance[i, j] = row[i] + col[i] - 2.0 * table[i, i]
                else:
                    covariance[i, j] = -(table[i, j] + table[j, i])
        if abs(np.linalg.det(covariance)) < 1e-12:
            raise StepError("bhapkar_test: covariance matrix is singular")
        stuart = float(delta @ np.linalg.solve(covariance, delta))
        denominator = 1.0 - stuart / total
        if denominator <= 0:
            raise StepError("bhapkar_test: correction denominator is non-positive")
        statistic = stuart / denominator
        df = r - 1
        p = float(stats.chi2.sf(statistic, df))
        out = scalar_form(
            [statistic, float(df), p, total, float(r)],
            ["statistic", "df", "p", "n", "n_categories"],
            "bhapkar_test",
        )
        out.info.update({"correction": "bhapkar", "stuart_maxwell_statistic": stuart})
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "df": int(df), "p": p,
            "n": int(total), "n_categories": int(r), "stuart_maxwell": stuart,
        }
        print(f"[bhapkar_test] chisq={statistic:.6f}, df={df}, p={p:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
