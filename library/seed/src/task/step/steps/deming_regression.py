"""Deming regression for two measurement methods."""
from __future__ import annotations

from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._stats20_common import scalar_form
from ._method33_common import deming, method_pairs


_NAMES = ["slope", "intercept", "n"]


class DemingRegressionStep(Step):
    provider = 'operon-core'
    parameters_file = 'deming_regression.DemingRegressionStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'deming_regression',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Deming regression',
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
     'description': 'Deming regression：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Method A、Method B、Error Ratio。'}

    def run(self, ctx: Context, inputs) -> None:
        x, y = method_pairs(
            inputs[0],
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("method_a", "method_a"),
            ctx.step_params.get("method_b", "method_b"),
            "deming_regression",
        )
        error_ratio = float(ctx.step_params.get("error_ratio", 1.0))
        slope, intercept, n = deming(x, y, error_ratio)
        form = scalar_form([slope, intercept, float(n)], _NAMES, "deming_regression")
        form.info.update({"method": "Deming", "error_ratio": error_ratio, "ci_method": "none", "n": n})
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "slope": slope, "intercept": intercept, "error_ratio": error_ratio, "n": n
        }
        print(f"[deming_regression] slope={slope:.6g} intercept={intercept:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
