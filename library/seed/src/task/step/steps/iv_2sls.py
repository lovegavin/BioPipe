"""Two-stage least squares instrumental-variable regression.

Estimates a linear structural equation with one or more endogenous
regressors, instrumented by exogenous instruments, optionally controlling
for exogenous regressors. The covariance is the homoskedastic plug-in
``sigma2 * inv(X' Pz X)`` with ``sigma2 = SSR / n``; this equals the
``unadjusted`` covariance reported by ``linearmodels.iv.IV2SLS``.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form, normal_p
from ._stats21_common import numeric_column, table_frame


class Iv2slsStep(Step):
    provider = 'operon-core'
    parameters_file = 'iv_2sls.Iv2slsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'iv_2sls',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Two-stage least squares',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {},
                'dims': [{'param': 'sample_dim', 'default': 'sample'},
                         {'param': 'feature_dim', 'default': 'feature'}],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'dependencies': [],
        'dependency_imports': [],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Two-stage least squares IV regression for a numeric table; instruments endogenous regressors.',
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        outcome_label = ctx.step_params["outcome_label"]
        endog = list(ctx.step_params["endog_labels"])
        instruments = list(ctx.step_params["instrument_labels"])
        exog = list(ctx.step_params.get("exog_labels") or [])
        add_constant = bool(ctx.step_params.get("add_constant", True))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if not 0.5 < confidence < 1.0:
            raise StepError("iv_2sls: confidence must be in (0.5, 1)")
        if not endog:
            raise StepError("iv_2sls: endog_labels must not be empty")
        if len(instruments) < len(endog):
            raise StepError("iv_2sls: need at least as many instruments as endogenous regressors")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        columns = {}
        for name in [outcome_label, *endog, *instruments, *exog]:
            columns[name] = numeric_column(frame, name, self.name)
        valid = np.ones(columns[outcome_label].size, dtype=bool)
        for values in columns.values():
            valid &= np.isfinite(values)
        y = columns[outcome_label][valid]
        n = int(y.size)
        if n < 5:
            raise StepError("iv_2sls: need at least five complete observations")

        blocks = [np.ones((n, 1))] if add_constant else []
        for name in exog:
            blocks.append(columns[name][valid][:, None])
        x = np.column_stack(blocks + [columns[name][valid][:, None] for name in endog])
        z = np.column_stack(blocks + [columns[name][valid][:, None] for name in instruments])

        if np.linalg.matrix_rank(z) < z.shape[1]:
            raise StepError("iv_2sls: instrument matrix is rank deficient")
        if np.linalg.matrix_rank(x) < x.shape[1]:
            raise StepError("iv_2sls: regressor matrix is rank deficient")

        # Project the regressors and the outcome on the instrument span without
        # forming the n-by-n projection matrix: A = (Z'Z)^-1 Z'X, b = (Z'Z)^-1 Z'y.
        ztz = z.T @ z
        a = np.linalg.solve(ztz, z.T @ x)
        b = np.linalg.solve(ztz, z.T @ y)
        xtpzx = x.T @ z @ a
        if np.linalg.matrix_rank(xtpzx) < x.shape[1]:
            raise StepError("iv_2sls: model is not identified by the supplied instruments")
        beta = np.linalg.solve(xtpzx, x.T @ z @ b)
        resid = y - x @ beta
        sigma2 = float(resid @ resid) / n
        cov = sigma2 * np.linalg.inv(xtpzx)
        se = np.sqrt(np.diag(cov))
        zstat = beta / se
        pvalue = normal_p(zstat)
        crit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        terms = (["const"] if add_constant else []) + exog + endog
        rows = np.column_stack([beta, se, zstat, pvalue,
                                beta - crit * se, beta + crit * se])
        labels = {
            "term": {name: index for index, name in enumerate(terms)},
            "statistic": {name: index for index, name in enumerate(
                ["coef", "se", "z", "p", "ci_low", "ci_high"])},
        }
        info = {
            "n_obs": n,
            "n_endog": len(endog),
            "n_instruments": len(instruments),
            "n_exog": len(exog),
            "add_constant": add_constant,
            "confidence": confidence,
            "sigma2": sigma2,
            "method": "2sls",
        }
        ctx[out_name] = make_form(rows, ["term", "statistic"], labels, info=info)

    def export(self, ctx: Context) -> dict:
        return {}
