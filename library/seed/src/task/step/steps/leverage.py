"""Leverage values from an ordinary least-squares design."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class LeverageStep(Step):
    provider = 'operon-core'
    parameters_file = 'leverage.LeverageStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'leverage',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'OLS leverage',
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
     'description': 'OLS leverage：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、响应变量。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response = ctx.step_params["response"]
        samples, predictors, _, _, _, leverage, _, _, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, "leverage"
        )
        form = Form(
            data=np.asarray(leverage, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={"sample": {name: i for i, name in enumerate(samples)}, "metric": {"leverage": 0}},
            info={"missing_code": np.nan, "response": response, "predictors": predictors, "p": int(p)},
        )
        form.validate()
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export_data = {
            "n": len(samples),
            "p": int(p),
            "response": response,
            "min_leverage": float(np.min(leverage)),
            "max_leverage": float(np.max(leverage)),
        }
        print(f"[leverage] n={len(samples)}, max={np.max(leverage):.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
