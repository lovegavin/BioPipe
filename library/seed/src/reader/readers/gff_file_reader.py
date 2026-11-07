"""GffFileReader: metadata-only GFF3 file source."""
from src.reader.base import Reader


class GffFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'gff_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
        'id': 'GffFileReader',
        'version': '1.0.0',
        'kind': 'reader',
        'title': 'GffFileReader',
        'description': 'Reference a GFF3 annotation file without parsing it into a table.',
        'category': 'Data',
        'icon': 'File',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'kind': 'file',
                'numeric': False,
                'ndim': 0,
                'info': {'representation': {'type': 'string', 'const': 'gff3'}},
                'info_open': True,
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'extensions': ['.gff3'],
        'handles_compression': True,
        'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']},
    }

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'gff3', **args)
