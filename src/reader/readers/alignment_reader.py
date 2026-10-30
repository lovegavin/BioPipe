"""AlignmentReader: a metadata-only file source."""
from src.reader.base import Reader


class AlignmentReader(Reader):
    provider = 'biopipe-hic'
    parameters_file = 'alignment.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'AlignmentReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'AlignmentReader',
     'description': 'Reference a disk dataset without loading its payload into memory.',
     'category': 'Hi-C',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'enum': ['sam', 'bam']}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.sam', '.bam'],
     'handles_compression': False,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': []}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'alignment', **args)
