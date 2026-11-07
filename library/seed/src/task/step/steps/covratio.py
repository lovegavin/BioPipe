"""COVRATIO influence statistic for an ordinary least-squares fit."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._influence66_common import influence_ols


class CovratioStep(Step):
    provider = 'operon-core'
    parameters_file = 'covratio.CovratioStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'covratio',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'COVRATIO',
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
     'description': 'COVRATIO：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、响应变量。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response = ctx.step_params["response"]
        out_name = ctx.step_params.get("output", self.name)
        samples, predictors, _, design, residuals, leverage, _, s2_i, p = influence_ols(
            inputs[0], sample_dim, feature_dim, response, "covratio"
        )
        n = design.shape[0]
        sigma_i = np.sqrt(s2_i)
        e_star = residuals / (sigma_i * np.sqrt(1.0 - leverage))
        denominator = (1.0 - leverage) * (((n - p - 1) + e_star * e_star) / (n - p)) ** p
        ratio = 1.0 / denominator
        form = Form(
            data=np.asarray(ratio, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "metric"],
            labels={"sample": {name: i for i, name in enumerate(samples)}, "metric": {"covratio": 0}},
            info={
                "missing_code": np.nan,
                "response": response,
                "predictors": predictors,
                "p": int(p),
                "n": int(n),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n": int(n),
            "p": int(p),
            "response": response,
            "predictors": predictors,
            "min_covratio": float(np.min(ratio)),
            "max_covratio": float(np.max(ratio)),
            "min_sample": samples[int(np.argmin(ratio))],
            "max_sample": samples[int(np.argmax(ratio))],
        }
        print(f"[covratio] n={n}, p={p}, range={np.min(ratio):.4g}..{np.max(ratio):.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
