"""Hi-C structure analysis."""
from src.task.step.base import Step


class AnalyzeContactsStep(Step):
    provider = 'biopipe-hic'
    parameters_file = 'analyze_contacts.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'analyze_contacts',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Hi-C structure analysis',
     'description': 'Hi-C structure analysis using versioned, logged external tools.',
     'category': 'analysis',
     'icon': 'Intersect',
     'dependencies': ['h5py>=3'],
     'inputs_arity': '*',
     'outputs': [],
     'output_parameter': 'output',
     'contracts': {'version': 1,
                   'inputs': [{'kind': ['file', 'form'],
                               'numeric': False,
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['cool',
                                                                    'hic_expected',
                                                                    'hic_compartments',
                                                                    'hic_insulation',
                                                                    'hic_loops']}}}],
                   'output': {'mode': 'choose',
                              'param': 'method',
                              'default': 'expected',
                              'cases': {'expected': {'mode': 'declare',
                                                     'schema': {'kind': 'form',
                                                                'numeric': True,
                                                                'ndim': 2,
                                                                'dims': ['record', 'statistic'],
                                                                'info': {'representation': {'type': 'string',
                                                                                            'const': 'hic_expected'}},
                                                                'info_open': True,
                                                                'axis_info_open': True}},
                                        'compartments': {'mode': 'declare',
                                                         'schema': {'kind': 'form',
                                                                    'numeric': True,
                                                                    'ndim': 2,
                                                                    'dims': ['record', 'statistic'],
                                                                    'info': {'representation': {'type': 'string',
                                                                                                'const': 'hic_compartments'}},
                                                                    'info_open': True,
                                                                    'axis_info_open': True}},
                                        'insulation': {'mode': 'declare',
                                                       'schema': {'kind': 'form',
                                                                  'numeric': True,
                                                                  'ndim': 2,
                                                                  'dims': ['record', 'statistic'],
                                                                  'info': {'representation': {'type': 'string',
                                                                                              'const': 'hic_insulation'}},
                                                                  'info_open': True,
                                                                  'axis_info_open': True}},
                                        'loops': {'mode': 'declare',
                                                  'schema': {'kind': 'form',
                                                             'numeric': True,
                                                             'ndim': 2,
                                                             'dims': ['record', 'statistic'],
                                                             'info': {'representation': {'type': 'string',
                                                                                         'const': 'hic_loops'}},
                                                             'info_open': True,
                                                             'axis_info_open': True}},
                                        'pileup': {'mode': 'declare',
                                                   'schema': {'kind': 'form',
                                                              'numeric': True,
                                                              'ndim': 2,
                                                              'dims': ['offset1', 'offset2'],
                                                              'info': {'representation': {'type': 'string',
                                                                                          'const': 'hic_pileup'}},
                                                              'info_open': True,
                                                              'axis_info_open': True}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory',
                   'external_tools': ['cooltools']}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return int(float(params.get('memory_mb', 256)) * 1024**2), 65536

    def run(self, ctx, inputs):
        from src.task.step.steps._hic_adapter import execute
        self._report = execute('analyze_contacts', ctx, inputs)

    def export(self, ctx):
        return self._report
