"""Holm step-down family-wise error adjustment."""
from __future__ import annotations

from src.task.context import Context
from src.task.step.base import Step
from ._p_adjust_common import adjust


class HolmAdjustStep(Step):
    provider = 'operon-core'
    """Holm step-down p-value adjustment; output feature x qvalue."""
    parameters_file = 'holm_adjust.HolmAdjustStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'holm_adjust',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Holm adjustment',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'value_dim', 'default': 'statistic'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Holm step-down p-value adjustment; output feature x qvalue.'}


    def run(self, ctx: Context, inputs) -> None:
        self._export_data = adjust(
            inputs[0], "holm",
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("value_dim", "pvalue"),
            self.name, ctx, self.name,
        )
        print(f"[holm_adjust] {self._export_data['n_tests']} tests")

    def export(self, ctx: Context) -> dict:
        return self._export_data
