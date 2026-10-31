"""Theil's uncertainty coefficient for a contingency table."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import reorder
from ._stats20_common import scalar_form


class TheilUStep(Step):
    name = "theil_u"
    title = "Theil's uncertainty coefficient"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("row_dim", "row"), param("column_dim", "column")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
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
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        out_name = ctx.step_params.get("output", self.name)
        data = np.asarray(reorder(inputs[0], row_dim, column_dim), dtype=np.float64)
        if data.ndim != 2 or min(data.shape) < 2:
            raise StepError("theil_u: a contingency table with at least 2 rows and 2 columns is required")
        if not np.isfinite(data).all() or np.any(data < 0):
            raise StepError("theil_u: counts must be finite and non-negative")
        total = float(data.sum())
        if total <= 0:
            raise StepError("theil_u: table total must be positive")
        row_sums = data.sum(axis=1)
        column_sums = data.sum(axis=0)
        if np.any(row_sums <= 0) or np.any(column_sums <= 0):
            raise StepError("theil_u: every row and column must have a positive total")

        def entropy(values):
            p = values[values > 0] / total
            return float(-np.sum(p * np.log(p)))

        h_row = entropy(row_sums)
        h_column = entropy(column_sums)
        h_joint = entropy(data.ravel())
        mutual = h_row + h_column - h_joint
        u_row = mutual / h_row
        u_column = mutual / h_column
        u_symmetric = 2.0 * mutual / (h_row + h_column)
        out = scalar_form(
            [u_row, u_column, u_symmetric, h_row, h_column, h_joint],
            ["u_row_given_column", "u_column_given_row", "u_symmetric", "h_row", "h_column", "h_joint"],
            "theil_u",
        )
        out.info.update({
            "n": total,
            "n_rows": int(data.shape[0]),
            "n_columns": int(data.shape[1]),
            "log_base": "natural",
        })
        ctx[out_name] = out
        self._export_data = {
            "u_row_given_column": u_row,
            "u_column_given_row": u_column,
            "u_symmetric": u_symmetric,
            "h_row": h_row,
            "h_column": h_column,
            "h_joint": h_joint,
            "n": total,
            "n_rows": int(data.shape[0]),
            "n_columns": int(data.shape[1]),
        }
        print(f"[theil_u] U(row|col)={u_row:.6g}, U(col|row)={u_column:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
