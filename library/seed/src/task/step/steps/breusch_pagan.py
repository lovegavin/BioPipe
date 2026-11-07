"""Breusch-Pagan heteroskedasticity test for a linear regression."""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form
from ._ext_common import labels_in_order, reorder, require_dims


class BreuschPaganStep(Step):
    provider = 'operon-core'
    parameters_file = 'breusch_pagan.BreuschPaganStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'breusch_pagan',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Breusch-Pagan test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'variable_dim', 'default': 'variable'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Breusch-Pagan test：接收 1 个输入，输出 Form；主要参数：样本维度、Variable Dim、响应变量、Regressors。'}

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
