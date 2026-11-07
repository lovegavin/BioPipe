"""TsvFileReader: pass a tabular text file through without parsing it."""
from src.reader.base import Reader


class TsvFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'tsv_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
        'id': 'TsvFileReader',
        'version': '1.0.0',
        'kind': 'reader',
        'title': 'TsvFileReader',
        'description': 'Reference a TSV/whitespace table without loading or decoding it.',
        'category': 'Data',
        'icon': 'File',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'kind': 'file',
                'numeric': False,
                'ndim': 0,
                'info': {'representation': {'type': 'string', 'const': 'tsv'}},
                'info_open': True,
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'extensions': ['.tsv', '.txt'],
        'handles_compression': True,
        'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']},
    }

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'tsv', **args)
