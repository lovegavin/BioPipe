"""Cohen's kappa for two raters on a contingency table."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.inter_rater import cohens_kappa

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form, table


_NAMES = ["kappa", "std_kappa", "z", "p", "ci_low", "ci_high"]


class CohensKappaStep(Step):
    name = "cohens_kappa"
    title = "Cohen's kappa"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("row_dim", "rater_a"), param("col_dim", "rater_b")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "rater_a"},
            "col_dim": {"type": "string", "default": "rater_b"},
            "weights": {"type": "string", "enum": ["none", "linear", "quadratic"], "default": "none"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, rows, cols = table(
            inputs[0], ctx.step_params.get("row_dim", "rater_a"),
            ctx.step_params.get("col_dim", "rater_b"), "cohens_kappa",
        )
        if np.any(data < 0):
            raise StepError("cohens_kappa: cell counts must be non-negative")
        weights = ctx.step_params.get("weights", "none")
        result = cohens_kappa(
            data,
            weights=None if weights == "none" else weights,
            return_results=True,
        )
        rows_out = [
            result.kappa, result.std_kappa, result.z_value, result.pvalue_two_sided,
            result.kappa_low, result.kappa_upp,
        ]
        form = scalar_form(rows_out, _NAMES, "cohens_kappa")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "kappa": float(result.kappa),
            "p": float(result.pvalue_two_sided),
            "weights": weights,
            "n_categories": int(data.shape[0]),
        }
        print(f"[cohens_kappa] kappa={result.kappa:.6g} p={result.pvalue_two_sided:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
