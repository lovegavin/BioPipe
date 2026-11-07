"""VcfFileReader: a metadata-only VCF file source.

The typed ``VcfReader`` decodes GT fields into a variant x sample genotype
matrix. Variant-file operators sometimes need the original text instead
(header, FILTER, INFO, exact line bytes), so this Reader passes the file
through as a ``FileArtifact`` without parsing it.
"""
from src.reader.base import Reader


class VcfFileReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'vcf_file.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
     'id': 'VcfFileReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'VcfFileReader',
     'description': 'Reference a VCF file without loading or decoding its records.',
     'category': 'Data',
     'icon': 'File',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'kind': 'file',
                              'numeric': False,
                              'ndim': 0,
                              'info': {'representation': {'type': 'string', 'const': 'vcf'}},
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.vcf'],
     'handles_compression': True,
     'file_input': {'dims': ['file'], 'labels': {}, 'compression': ['.gz', '.bz2', '.xz']}}

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source
        return read_file_source(path, 'vcf', **args)
