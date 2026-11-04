"""Hi-C read alignment."""
from src.task.step.base import Step


class AlignReadsStep(Step):
    provider = 'biopipe-hic'
    parameters_file = 'align_reads.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'align_reads',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Hi-C read alignment',
     'description': 'Hi-C read alignment using versioned, logged external tools.',
     'category': 'data preparation',
     'icon': 'ArrowsIn',
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'contracts': {'version': 1,
                   'inputs': [{'kind': 'file',
                               'numeric': False,
                               'info': {'representation': {'type': 'string', 'enum': ['fastq']}}}],
                   'output': {'mode': 'declare',
                              'schema': {'kind': 'file',
                                         'numeric': False,
                                         'ndim': 0,
                                         'dims': [],
                                         'info': {'representation': {'type': 'string', 'const': 'bam'}},
                                         'info_open': True}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory',
                   'external_tools': ['bwa', 'samtools']}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return int(float(params.get('memory_mb', 256)) * 1024**2), 65536

    def run(self, ctx, inputs):
        from src.task.step.steps._hic_adapter import execute
        self._report = execute('align_reads', ctx, inputs)

    def export(self, ctx):
        return self._report
