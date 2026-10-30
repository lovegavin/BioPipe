"""Goodman-Kruskal gamma for a contingency table."""
from __future__ import annotations

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ordinal38_common import contingency, goodman_kruskal_gamma
from ._stats20_common import scalar_form


class GoodmanKruskalGammaStep(Step):
    """Goodman-Kruskal gamma, the symmetric ordinal association measure."""

    name = "goodman_kruskal_gamma"
    title = "Goodman-Kruskal gamma"
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
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        out_name = ctx.step_params.get("output", self.name)
        counts, rows, columns = contingency(form, row_dim, column_dim, "goodman_kruskal_gamma")
        value, concordant, discordant = goodman_kruskal_gamma(counts)
        total = float(counts.sum())
        out = scalar_form(
            [value, concordant, discordant, total, float(len(rows)), float(len(columns))],
            ["gamma", "concordant", "discordant", "n", "n_rows", "n_columns"],
            "goodman_kruskal_gamma",
        )
        out.info.update({"row_labels": rows, "column_labels": columns})
        ctx[out_name] = out
        self._export_data = {
            "gamma": value,
            "concordant": float(concordant),
            "discordant": float(discordant),
            "n": int(total),
        }
        print(f"[goodman_kruskal_gamma] gamma={value:.6f}, n={total:.0f}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
