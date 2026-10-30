"""Quade test for an unreplicated complete block design."""
from __future__ import annotations

import numpy as np
from scipy import stats, special

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class QuadeTestStep(Step):
    """Quade rank test for a complete block design.

    Each block is ranked internally, blocks are weighted by their range, and
    the resulting F statistic matches ``stats::quade.test``.
    """

    name = "quade_test"
    title = "Quade test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("block_dim", "block"), param("treatment_dim", "treatment")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "block_dim": {"type": "string", "default": "block"},
            "treatment_dim": {"type": "string", "default": "treatment"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        block_dim = ctx.step_params.get("block_dim", "block")
        treatment_dim = ctx.step_params.get("treatment_dim", "treatment")
        if form.data.ndim != 2:
            raise StepError(f"expected a 2D form, got ndim={form.data.ndim}")
        if block_dim not in form.dims or treatment_dim not in form.dims:
            raise StepError(
                f"expected dims {block_dim!r} and {treatment_dim!r}, got {form.dims}"
            )
        axis = form.dims.index(block_dim)
        y = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
        if y.ndim != 2 or y.shape[0] < 2 or y.shape[1] < 2:
            raise StepError("quade_test needs at least two blocks and two treatments")
        if not np.all(np.isfinite(y)):
            raise StepError("quade_test does not accept missing values")
        blocks, treatments = y.shape
        ranks = np.vstack([stats.rankdata(row, method="average") for row in y])
        ranges = y.max(axis=1) - y.min(axis=1)
        block_weights = stats.rankdata(ranges, method="average")
        scores = block_weights[:, None] * (ranks - (treatments + 1.0) / 2.0)
        a_value = float(np.sum(scores**2))
        b_value = float(np.sum(scores.sum(axis=0) ** 2) / blocks)
        if a_value == b_value:
            statistic = float("nan")
            df1 = float(treatments - 1)
            df2 = float((blocks - 1) * (treatments - 1))
            p_value = float(special.gamma(treatments + 1.0) ** (1.0 - blocks))
        else:
            statistic = float((blocks - 1) * b_value / (a_value - b_value))
            df1 = float(treatments - 1)
            df2 = float((blocks - 1) * (treatments - 1))
            p_value = float(stats.f.sf(statistic, df1, df2))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(
                [[statistic], [df1], [df2], [p_value], [blocks], [treatments]],
                dtype=np.float32,
            ),
            dims=["statistic", "value"],
            labels={
                "statistic": {
                    "F": 0,
                    "df1": 1,
                    "df2": 2,
                    "p": 3,
                    "n_blocks": 4,
                    "n_treatments": 5,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "method": "Quade"},
        )
        self._export_data = {
            "F": statistic,
            "df1": int(df1),
            "df2": int(df2),
            "p": p_value,
            "n_blocks": blocks,
            "n_treatments": treatments,
        }
        print(f"[quade_test] {blocks} blocks, {treatments} treatments, F={statistic}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
