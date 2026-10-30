"""Fleiss' kappa for several raters on a subject x category count table."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.inter_rater import fleiss_kappa

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form, table


class FleissKappaStep(Step):
    name = "fleiss_kappa"
    title = "Fleiss' kappa"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("subject_dim", "subject"), param("category_dim", "category")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "subject_dim": {"type": "string", "default": "subject"},
            "category_dim": {"type": "string", "default": "category"},
            "method": {"type": "string", "enum": ["fleiss", "randolph"], "default": "fleiss"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, subjects, categories = table(
            inputs[0], ctx.step_params.get("subject_dim", "subject"),
            ctx.step_params.get("category_dim", "category"), "fleiss_kappa",
        )
        if np.any(data < 0):
            raise StepError("fleiss_kappa: cell counts must be non-negative")
        method = ctx.step_params.get("method", "fleiss")
        kappa = float(fleiss_kappa(data, method=method))
        form = scalar_form([kappa, len(subjects), len(categories)],
                           ["kappa", "n_subjects", "n_categories"], "fleiss_kappa")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"kappa": kappa, "method": method,
                        "n_subjects": len(subjects), "n_categories": len(categories)}
        print(f"[fleiss_kappa] kappa={kappa:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
