"""9-column broadPeak reader."""
from __future__ import annotations

from pathlib import Path

from src.reader.base import Reader
from ._table_common import read_whitespace, table_form


class BroadPeakReader(Reader):
    provider = 'operon-readers'
    """Reader for broadPeak files; output is region x field."""
    parameters_file = 'broadpeak_reader.BroadPeakReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BroadPeakReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for broadPeak files; output is region x field',
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
     'description': 'Reader for broadPeak files; output is region x field.',
     'extensions': ['.broadpeak'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        names = [
            "chrom", "start", "end", "name", "score", "strand",
            "signal_value", "p_value", "q_value",
        ]
        df = read_whitespace(path, names, "broadPeak")
        return table_form(df, dims, labels, "broadPeak", args.get("encoders", {}))
