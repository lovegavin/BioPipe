"""Brown-Forsythe test for equality of variances across groups."""
from __future__ import annotations

from src.task.context import Context

from .levene_test import LeveneTestStep


class BrownForsytheStep(LeveneTestStep):
    provider = 'operon-core'
    """Median-centered Levene test, known as the Brown-Forsythe test."""
    parameters_file = 'brown_forsythe.BrownForsytheStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'brown_forsythe',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Brown-Forsythe variance test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'group_dim', 'default': 'sample'},
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
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Median-centered Levene test, known as the Brown-Forsythe test.'}

    test_label = "Brown-Forsythe"

    def run(self, ctx: Context, inputs) -> None:
        self._run_variance(ctx, inputs, "median")
