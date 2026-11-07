"""BamFileReader: a metadata-only BAM file source.

The typed ``BamReader`` decodes alignments into a read x field matrix.
Alignment-level operators sometimes need the binary records themselves
(flags, mapping positions, CIGAR strings), so this Reader passes the file
through as a ``FileArtifact`` without decoding it.
"""
from src.reader.base import Reader


class BamFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'bam_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BamFileReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'BamFileReader',
     'description': 'Reference a BAM file without loading or decoding its records.',
     'category': 'Data',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'bam'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.bam'],
     'handles_compression': False,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': []}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'bam', **args)
