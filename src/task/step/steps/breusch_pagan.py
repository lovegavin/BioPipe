"""Breusch-Pagan heteroskedasticity test for a linear regression."""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form
from ._ext_common import labels_in_order, reorder, require_dims


class BreuschPaganStep(Step):
    name = "breusch_pagan"
    title = "Breusch-Pagan test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("variable_dim", "variable")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "variable_dim": {"type": "string", "default": "variable"},
            "response": {"type": "string"},
            "regressors": {"type": "array", "items": {"type": "string"}},
            "output": {"type": "string"},
        },
        "required": ["response"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        variable_dim = ctx.step_params.get("variable_dim", "variable")
        require_dims(form, sample_dim, variable_dim, label="breusch_pagan")
        data = reorder(form, sample_dim, variable_dim)
        variables = labels_in_order(form, variable_dim)
        response = ctx.step_params["response"]
        if response not in variables:
            raise StepError(f"breusch_pagan: response {response!r} not in {variables}")
        chosen = ctx.step_params.get("regressors")
        if chosen is None:
            regressors = [name for name in variables if name != response]
        else:
            regressors = list(chosen)
            missing = [name for name in regressors if name not in variables]
            if missing:
                raise StepError(f"breusch_pagan: regressors not found: {missing}")
            if response in regressors:
                raise StepError("breusch_pagan: response cannot also be a regressor")
        if not regressors:
            raise StepError("breusch_pagan: at least one regressor is required")
        ri = variables.index(response)
        xi = [variables.index(name) for name in regressors]
        y = data[:, ri]
        X = data[:, xi]
        mask = np.isfinite(y) & np.isfinite(X).all(axis=1)
        y = y[mask]
        X = X[mask]
        if len(y) < len(regressors) + 2:
            raise StepError("breusch_pagan: not enough complete observations")
        design = sm.add_constant(X, has_constant="add")
        fitted = sm.OLS(y, design).fit()
        lm, lm_p, f_stat, f_p = het_breuschpagan(fitted.resid, design)
        rows = [lm, lm_p, f_stat, f_p, len(y)]
        form_out = scalar_form(rows, ["lm_statistic", "lm_p", "f_statistic", "f_p", "n"], "breusch_pagan")
        ctx[ctx.step_params.get("output", self.name)] = form_out
        self._export = {
            "lm_statistic": float(lm), "lm_p": float(lm_p),
            "f_statistic": float(f_stat), "f_p": float(f_p),
            "n": int(len(y)), "response": response, "regressors": regressors,
        }
        print(f"[breusch_pagan] LM={lm:.6g} p={lm_p:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
