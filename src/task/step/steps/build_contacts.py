"""Build contact map."""
from src.task.step.base import Step


class BuildContactsStep(Step):
    provider = 'biopipe-hic'
    parameters_file = 'build_contacts.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'build_contacts',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Build contact map',
     'description': 'Build contact map using versioned, logged external tools.',
     'category': 'data preparation',
     'icon': 'GridNine',
     'dependencies': ['h5py>=3'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'contracts': {'version': 1,
                   'inputs': [{'kind': 'file',
                               'numeric': False,
                               'info': {'representation': {'type': 'string',
                                                           'enum': ['sam', 'bam', 'pairs']}}}],
                   'output': {'mode': 'declare',
                              'schema': {'kind': 'file',
                                         'numeric': False,
                                         'ndim': 0,
                                         'dims': [],
                                         'info': {'representation': {'type': 'string',
                                                                     'const': 'cool'}},
                                         'info_open': True}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory',
                   'external_tools': ['pairtools', 'cooler', 'samtools']}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return int(float(params.get('memory_mb', 256)) * 1024**2), 65536

    def run(self, ctx, inputs):
        from src.task.step.steps._hic_adapter import execute
        self._report = execute('build_contacts', ctx, inputs)

    def export(self, ctx):
        return self._report
