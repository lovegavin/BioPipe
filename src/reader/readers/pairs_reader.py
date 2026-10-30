"""PairsReader: a metadata-only file source."""
from src.reader.base import Reader


class PairsReader(Reader):
    provider = 'biopipe-hic'
    parameters_file = 'pairs.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'PairsReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'PairsReader',
     'description': 'Reference a disk dataset without loading its payload into memory.',
     'category': 'Hi-C',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'pairs'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.pairs'],
     'handles_compression': True,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'pairs', **args)
