"""Negative-binomial (NB2) regression for over-dispersed counts."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._count_common import count_design, result_rows
from ._ext_common import make_form


class NegativeBinomialRegressionStep(Step):
    provider = 'operon-core'
    parameters_file = 'negative_binomial_regression.NegativeBinomialRegressionStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'negative_binomial_regression',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Negative-binomial regression',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Negative-binomial regression：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Response '
                    'Label、Predictors、分类协变量、Maxiter。'}

    def run(self, ctx: Context, inputs) -> None:
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        maxiter = int(ctx.step_params.get("maxiter", 200))
        out_name = ctx.step_params.get("output", self.name)

        frame, response, design, terms = count_design(
            inputs[0], sample_dim, feature_dim, response_label, predictors, categorical, self.name
        )
        try:
            result = sm.NegativeBinomial(response, design, loglike_method="nb2").fit(
                start_params=None, maxiter=maxiter, disp=0
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        n_terms = len(terms)
        if params.size < n_terms + 1:
            raise StepError(f"{self.name}: unexpected parameter vector length")
        alpha = float(params[-1])
        rows = result_rows(params[:n_terms], bse[:n_terms], pvalues[:n_terms], conf[:n_terms], terms)
        block = np.asarray(rows, dtype=np.float32)
        ctx[out_name] = make_form(
            block,
            ["term", "statistic"],
            {
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "rate_ratio": 6,
                    "RR_CI_low": 7,
                    "RR_CI_high": 8,
                },
            },
            info={
                "method": "negative binomial NB2",
                "n": int(response.size),
                "alpha": alpha,
                "llf": float(result.llf),
                "aic": float(result.aic),
                "terms": terms,
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in params[:n_terms]],
            "se": [float(value) for value in bse[:n_terms]],
            "p": [float(value) for value in pvalues[:n_terms]],
            "rate_ratio": [float(value) for value in np.exp(params[:n_terms])],
            "alpha": alpha,
            "llf": float(result.llf),
            "aic": float(result.aic),
            "n": int(response.size),
        }
        print(f"[{self.name}] n={response.size}, terms={len(terms)}, alpha={alpha:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
