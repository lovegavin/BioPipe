"""Cytogenetic band reader.

Reads the five-column UCSC cytoband table:
chrom, start, end, band name and stain."""
from __future__ import annotations

from pathlib import Path


from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import read_whitespace, table_form


class CytobandReader(Reader):
    provider = 'operon-readers'
    """Cytogenetic band reader."""
    parameters_file = 'cytoband_reader.CytobandReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'CytobandReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Cytogenetic band reader',
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
     'description': 'Cytogenetic band reader.',
     'extensions': ['.cytoband'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"cytoband reader requires exactly two dims, got {dims}")
        df = df = read_whitespace(path, ["chrom", "start", "end", "name", "stain"], "cytoband")
        return table_form(
            df, dims, labels, "cytoband",
            encoders_cfg=args.get("encoders") or {},
        )
