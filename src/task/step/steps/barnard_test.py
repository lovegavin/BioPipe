"""Barnard exact unconditional test for a 2x2 table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, require_dims


class BarnardTestStep(Step):
    """Barnard's exact unconditional test of independence in a 2x2 table.

    The p-value is computed with SciPy's unconditional exact algorithm,
    which maximises over the nuisance success probability.
    """

    name = "barnard_test"
    title = "Barnard exact test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("row_dim", "row"), param("column_dim", "column")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 1, "numeric": True, "info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "row"},
            "column_dim": {"type": "string", "default": "column"},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "less", "greater"],
                "default": "two-sided",
            },
            "pooled": {"type": "boolean", "default": True},
            "integration_points": {"type": "integer", "minimum": 1, "maximum": 4096, "default": 32},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        (form,) = inputs
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        require_dims(form, row_dim, column_dim, label="input")
        row_axis = form.dims.index(row_dim)
        column_axis = form.dims.index(column_dim)
        if row_axis == column_axis:
            raise StepError("barnard_test: row_dim and column_dim must differ")
        table = np.transpose(np.asarray(form.data, dtype=np.float64), [row_axis, column_axis])
        if table.shape != (2, 2):
            raise StepError(f"barnard_test needs a 2x2 table, got {table.shape}")
        if not np.all(np.isfinite(table)):
            raise StepError("barnard_test: table contains missing or non-finite values")
        rounded = np.rint(table)
        if not np.allclose(table, rounded):
            raise StepError("barnard_test: table counts must be integers")
        if np.any(rounded < 0):
            raise StepError("barnard_test: table counts must be non-negative")
        table_int = rounded.astype(np.int64)
        if table_int.sum() == 0:
            raise StepError("barnard_test: table is empty")
        if np.any(table_int.sum(axis=0) == 0) or np.any(table_int.sum(axis=1) == 0):
            raise StepError("barnard_test: every row and column needs a non-zero margin")
        alternative = ctx.step_params.get("alternative", "two-sided")
        pooled = bool(ctx.step_params.get("pooled", True))
        points = int(ctx.step_params.get("integration_points", 32))
        result = stats.barnard_exact(
            table_int,
            alternative=alternative,
            pooled=pooled,
            n=points,
        )
        fisher = stats.fisher_exact(table_int, alternative=alternative)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(
                [float(result.statistic), float(result.pvalue), float(fisher.statistic), int(table_int.sum())],
                dtype=np.float32,
            ),
            dims=["statistic"],
            labels={
                "statistic": {
                    "statistic": 0,
                    "p": 1,
                    "odds_ratio": 2,
                    "n": 3,
                }
            },
            info={
                "missing_code": np.nan,
                "test": "Barnard",
                "alternative": alternative,
                "pooled": pooled,
                "integration_points": points,
                "method": "SciPy unconditional exact",
                "rows": labels_in_order(form, row_dim),
                "columns": labels_in_order(form, column_dim),
            },
        )
        self._export_data = {
            "statistic": float(result.statistic),
            "p": float(result.pvalue),
            "odds_ratio": float(fisher.statistic),
            "n": int(table_int.sum()),
            "alternative": alternative,
            "pooled": pooled,
        }
        print(f"[barnard_test] p={float(result.pvalue):.6g}, n={int(table_int.sum())}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
