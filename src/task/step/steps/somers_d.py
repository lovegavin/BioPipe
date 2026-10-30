"""Somers' D ordinal association for a contingency table."""
from __future__ import annotations

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ordinal38_common import contingency, somers_d
from ._stats20_common import scalar_form


class SomersDStep(Step):
    """Somers' D with the row or column variable as dependent."""

    name = "somers_d"
    title = "Somers' D"
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
            "direction": {"type": "string", "enum": ["row", "column"], "default": "row"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        direction = ctx.step_params.get("direction", "row")
        out_name = ctx.step_params.get("output", self.name)
        counts, rows, columns = contingency(form, row_dim, column_dim, "somers_d")
        value, concordant, discordant, denominator = somers_d(counts, direction)
        total = float(counts.sum())
        out = scalar_form(
            [value, concordant, discordant, denominator, total, float(len(rows)), float(len(columns))],
            ["D", "concordant", "discordant", "comparable_pairs", "n", "n_rows", "n_columns"],
            "somers_d",
        )
        out.info.update({"direction": direction, "row_labels": rows, "column_labels": columns})
        ctx[out_name] = out
        self._export_data = {
            "D": value,
            "concordant": float(concordant),
            "discordant": float(discordant),
            "comparable_pairs": float(denominator),
            "n": int(total),
            "direction": direction,
        }
        print(f"[somers_d] D={value:.6f}, direction={direction}, n={total:.0f}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
