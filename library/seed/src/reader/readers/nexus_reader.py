"""NEXUS alignment reader.

Reads a simple NEXUS DATA block with a non-interleaved MATRIX. The
matrix may contain DNA or protein characters; gaps become NaN and
unknown characters use code 5.
"""
from __future__ import annotations

from pathlib import Path

from src.core import ReaderError
from src.reader.base import Reader
from src.reader.readers._alignment_common import alignment_form, read_nexus


class NexusReader(Reader):
    provider = 'operon-readers'
    """Reader for .nex / .nexus alignments."""
    parameters_file = 'nexus_reader.NexusReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'NexusReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for .nex / .nexus alignments',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Reader for .nex / .nexus alignments.',
     'extensions': ['.nex', '.nexus'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sequence', 'position'],
                    'labels': {'sequence': 'builtin', 'position': 'auto'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        ids, seqs = read_nexus(path)
        if not ids:
            raise ReaderError("Nexus reader: no MATRIX sequences found")
        return alignment_form(ids, seqs, dims, labels, "nexus")
