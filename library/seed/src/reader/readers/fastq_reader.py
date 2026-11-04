"""FastqReader: a metadata-only file source."""
from src.reader.base import Reader


class FastqReader(Reader):
    provider = 'biopipe-hic'
    parameters_file = 'fastq.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'FastqReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'FastqReader',
     'description': 'Reference a disk dataset without loading its payload into memory.',
     'category': 'Hi-C',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'fastq'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.fastq', '.fq'],
     'handles_compression': True,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'fastq', **args)
