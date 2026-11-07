"""FastaFileReader: a metadata-only FASTA file source.

The typed ``FastaReader`` decodes sequences into a Form. Alignment and variant
operators sometimes need the raw file path so a subprocess or their own parser
can stream it, so this Reader passes the file through as a ``FileArtifact``.
"""
from src.reader.base import Reader


class FastaFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'fasta_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
     'id': 'FastaFileReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'FastaFileReader',
     'description': 'Reference a FASTA file without loading or decoding its sequences.',
     'category': 'Data',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'fasta'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.fasta', '.fa', '.fna', '.fas'],
     'handles_compression': True,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'fasta', **args)
