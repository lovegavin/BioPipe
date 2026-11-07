"""Cook's distance for an ordinary least-squares fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class CooksDistanceStep(Step):
    provider = 'operon-core'
    parameters_file = 'cooks_distance.CooksDistanceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cooks_distance',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cook's distance",
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
     'description': "Cook's distance：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、响应变量。"}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response = ctx.step_params["response"]
        samples, predictors, _, _, residuals, leverage, mse, _, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, "cooks_distance"
        )
        distance = residuals * residuals / (p * mse) * leverage / ((1.0 - leverage) ** 2)
        form = Form(
            data=np.asarray(distance, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={"sample": {name: i for i, name in enumerate(samples)}, "metric": {"cooks_distance": 0}},
            info={"missing_code": np.nan, "response": response, "predictors": predictors, "p": int(p)},
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export_data = {
            "n": len(samples),
            "p": int(p),
            "response": response,
            "max_distance": float(np.max(distance)),
            "max_sample": samples[int(np.argmax(distance))],
        }
        print(f"[cooks_distance] n={len(samples)}, max={np.max(distance):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
