"""Conger's kappa agreement coefficient."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._agreement68_common import (
    coefficient,
    conger_pe,
    observed_agreement,
    rating_matrix,
)


class CongerKappaStep(Step):
    name = "conger_kappa"
    title = "Conger's kappa"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("subject_dim", "subject"), param("rater_dim", "rater")])
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "subject_dim": {"type": "string", "default": "subject"},
            "rater_dim": {"type": "string", "default": "rater"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        subject_dim = ctx.step_params.get("subject_dim", "subject")
        rater_dim = ctx.step_params.get("rater_dim", "rater")
        matrix, values, counts, rated = rating_matrix(inputs[0], subject_dim, rater_dim, self.name)
        pa = observed_agreement(counts, rated)
        pe = conger_pe(matrix, values)
        kappa = coefficient(pa, pe, self.name)
        data = np.asarray([[kappa, pa, pe, matrix.shape[0], matrix.shape[1], values.size]], dtype=np.float64)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["metric", "statistic"],
            labels={
                "metric": {"conger_kappa": 0},
                "statistic": {
                    "conger_kappa": 0,
                    "pa": 1,
                    "pe": 2,
                    "n_subjects": 3,
                    "n_raters": 4,
                    "n_categories": 5,
                },
            },
            info={"missing_code": np.nan, "weights": "unweighted"},
        )
        self._export_data = {
            "conger_kappa": kappa,
            "pa": pa,
            "pe": pe,
            "n_subjects": int(matrix.shape[0]),
            "n_raters": int(matrix.shape[1]),
            "n_categories": int(values.size),
        }
        print(f"[conger_kappa] kappa={kappa:.4g}, pa={pa:.4g}, pe={pe:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
