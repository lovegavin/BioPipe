"""ChainFileReader: a metadata-only UCSC chain file source."""
from src.reader.base import Reader


class ChainFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'chain_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ChainFileReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'ChainFileReader',
     'description': 'Reference a UCSC chain file without parsing it in the reader layer.',
     'category': 'Data',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'chain'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.chain', '.chain.gz'],
     'handles_compression': True,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz']}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'chain', **args)
