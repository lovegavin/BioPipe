"""CoolerReader: a metadata-only file source."""
from src.reader.base import Reader


class CoolerReader(Reader):
    provider = 'biopipe-hic'
    parameters_file = 'cooler.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'CoolerReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'CoolerReader',
     'description': 'Reference a disk dataset without loading its payload into memory.',
     'category': 'Hi-C',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'cool'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.cool', '.mcool'],
     'handles_compression': False,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': []},
     'dependencies': ['h5py>=3.0'],
     'dependency_imports': ['h5py']}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'cool', **args)
