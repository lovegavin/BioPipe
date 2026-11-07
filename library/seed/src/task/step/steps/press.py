"""Prediction error sum of squares (PRESS) for an OLS fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class PressStep(Step):
    provider = 'operon-core'
    parameters_file = 'press.PressStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'press',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Prediction error sum of squares',
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
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Prediction error sum of squares：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、响应变量。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response = ctx.step_params["response"]
        samples, predictors, _, _, residuals, leverage, _, _, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, self.name
        )
        deleted = residuals / (1.0 - leverage)
        press = float(np.sum(deleted * deleted))
        n = len(samples)
        rmse = float(np.sqrt(press / n))
        form = Form(
            data=np.asarray([[press, rmse, float(n), float(p)]], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"press": 0},
                "statistic": {"press": 0, "press_rmse": 1, "n": 2, "p": 3},
            },
            info={"missing_code": np.nan, "response": response, "predictors": predictors},
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export_data = {
            "press": press,
            "press_rmse": rmse,
            "n": int(n),
            "p": int(p),
            "response": response,
        }
        print(f"[press] n={n}, PRESS={press:.4g}, RMSE={rmse:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
