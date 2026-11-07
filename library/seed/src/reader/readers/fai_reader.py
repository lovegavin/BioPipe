"""SAM/FASTA .fai index reader."""
from __future__ import annotations

from pathlib import Path

from src.reader.base import Reader
from ._table_common import read_whitespace, table_form


class FaiReader(Reader):
    provider = 'operon-readers'
    """Reader for 5-column .fai sequence index files."""
    parameters_file = 'fai_reader.FaiReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'FaiReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for 5-column .fai sequence index files',
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
     'description': 'Reader for 5-column .fai sequence index files.',
     'extensions': ['.fai'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['record', 'field'], 'labels': {'record': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        df = read_whitespace(path, ["name", "length", "offset", "linebases", "linewidth"], "FAI")
        return table_form(df, dims, labels, "FAI", args.get("encoders", {}))
