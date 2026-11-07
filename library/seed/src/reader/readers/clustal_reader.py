"""Clustal alignment reader.

Parses CLUSTAL/MUSCLE block alignments into a sequence x position
numeric matrix. Gaps (``-`` and ``.``) become NaN; nucleotides use the
same codes as the FASTA reader.
"""
from __future__ import annotations

from pathlib import Path

from src.core import ReaderError
from src.reader.base import Reader
from src.reader.readers._alignment_common import alignment_form, read_clustal


class ClustalReader(Reader):
    provider = 'operon-readers'
    """Reader for .aln / .clustal block alignments."""
    parameters_file = 'clustal_reader.ClustalReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ClustalReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for .aln / .clustal block alignments',
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
     'description': 'Reader for .aln / .clustal block alignments.',
     'extensions': ['.aln', '.clustal'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sequence', 'position'],
                    'labels': {'sequence': 'builtin', 'position': 'auto'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        ids, seqs = read_clustal(path)
        if not ids:
            raise ReaderError("Clustal reader: no aligned sequences found")
        return alignment_form(ids, seqs, dims, labels, "clustal")
