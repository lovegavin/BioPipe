"""Inverse-probability-of-treatment weighting (IPTW) effect estimate.

Fits a logistic propensity model with ``statsmodels`` and reports the
weighted mean outcome difference for the average treatment effect (ATE)
or the average treatment effect on the treated (ATT). The standard error
is a heteroskedasticity-robust (HC0) sandwich from the weighted outcome
regression, treating the estimated weights as fixed.
"""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form, normal_p
from ._stats21_common import numeric_column, table_frame


class IptwEffectStep(Step):
    provider = 'operon-core'
    parameters_file = 'iptw_effect.IptwEffectStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'iptw_effect',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'IPTW treatment effect',
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
        'dependencies': ['statsmodels>=0.14'],
        'dependency_imports': ['statsmodels'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Inverse-probability-of-treatment weighting estimate of an average treatment effect.',
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        treatment_label = ctx.step_params["treatment_label"]
        outcome_label = ctx.step_params["outcome_label"]
        covariates = list(ctx.step_params.get("covariate_labels") or [])
        estimand = ctx.step_params.get("estimand", "ate")
        trim = float(ctx.step_params.get("trim", 0.0))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if estimand not in {"ate", "att"}:
            raise StepError("iptw_effect: estimand must be 'ate' or 'att'")
        if not 0.0 <= trim < 0.5:
            raise StepError("iptw_effect: trim must be in [0, 0.5)")
        if not 0.5 < confidence < 1.0:
            raise StepError("iptw_effect: confidence must be in (0.5, 1)")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        treatment = numeric_column(frame, treatment_label, self.name)
        outcome = numeric_column(frame, outcome_label, self.name)
        covariate_values = [numeric_column(frame, name, self.name) for name in covariates]
        valid = np.isfinite(treatment) & np.isfinite(outcome)
        for values in covariate_values:
            valid &= np.isfinite(values)
        treatment = treatment[valid]
        outcome = outcome[valid]
        covariate_values = [values[valid] for values in covariate_values]
        n = int(treatment.size)
        if n < 6:
            raise StepError("iptw_effect: need at least six complete observations")
        if not np.all(np.isin(np.unique(treatment), (0.0, 1.0))):
            raise StepError("iptw_effect: treatment must be coded 0/1")
        treated = treatment == 1.0
        n_treated = int(treated.sum())
        n_control = n - n_treated
        if n_treated < 2 or n_control < 2:
            raise StepError("iptw_effect: need at least two treated and two control samples")

        design = np.column_stack([np.ones(n)] + [values[:, None] for values in covariate_values])
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError("iptw_effect: covariate matrix is rank deficient")
        model = sm.GLM(treatment, design, family=sm.families.Binomial()).fit()
        propensity = np.clip(np.asarray(model.fittedvalues, dtype=np.float64), 1e-9, 1.0 - 1e-9)
        if trim > 0.0:
            propensity = np.clip(propensity, trim, 1.0 - trim)
        if estimand == "ate":
            weights = np.where(treated, 1.0 / propensity, 1.0 / (1.0 - propensity))
        else:
            weights = np.where(treated, 1.0, propensity / (1.0 - propensity))

        outcome_design = np.column_stack([np.ones(n), treatment])
        xtwx = outcome_design.T @ (outcome_design * weights[:, None])
        bread = np.linalg.inv(xtwx)
        beta = bread @ (outcome_design.T @ (weights * outcome))
        resid = outcome - outcome_design @ beta
        meat = outcome_design.T @ (
            outcome_design * (weights * weights * resid * resid)[:, None]
        )
        cov = bread @ meat @ bread
        estimate = float(beta[1])
        se = float(np.sqrt(cov[1, 1]))
        if not np.isfinite(estimate) or not np.isfinite(se) or se <= 0.0:
            raise StepError("iptw_effect: the weighted estimate is not finite")
        zstat = estimate / se
        pvalue = float(normal_p(np.asarray(zstat)))
        crit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        rows = np.array([
            [estimate],
            [se],
            [zstat],
            [pvalue],
            [estimate - crit * se],
            [estimate + crit * se],
            [n_treated],
            [n_control],
            [float(propensity.min())],
            [float(propensity.max())],
        ], dtype=np.float64)
        labels = {
            "statistic": {name: index for index, name in enumerate(
                ["effect", "se", "z", "p", "ci_low", "ci_high",
                 "n_treated", "n_control", "ps_min", "ps_max"])},
            "value": {"value": 0},
        }
        info = {
            "estimand": estimand,
            "n_obs": n,
            "n_covariates": len(covariates),
            "trim": trim,
            "confidence": confidence,
            "method": "iptw",
        }
        ctx[out_name] = make_form(rows, ["statistic", "value"], labels, info=info)

    def export(self, ctx: Context) -> dict:
        return {}
