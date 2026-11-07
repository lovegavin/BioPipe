"""PAF reader.

Reads the 12 mandatory PAF columns (query/target names and
coordinates, strand, alignment block length, matches and mapping
quality). Optional SAM-style tags are ignored."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class PafReader(Reader):
    provider = 'operon-readers'
    """Pairwise mapping format (PAF) reader."""
    parameters_file = 'paf_reader.PafReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PafReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Pairwise mapping format (PAF) reader',
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
     'description': 'Pairwise mapping format (PAF) reader.',
     'extensions': ['.paf'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PAF reader requires exactly two dims, got {dims}")
        df = pd.read_csv(path, sep="\t", header=None, comment="#")
        if df.shape[1] < 12:
            raise ReaderError(f"PAF reader: expected at least 12 columns, got {df.shape[1]}")
        df = df.iloc[:, :12]
        df.columns = ["query_name", "query_length", "query_start", "query_end",
                      "strand", "target_name", "target_length", "target_start",
                      "target_end", "matches", "block_length", "mapq"]
        return table_form(
            df, dims, labels, "PAF",
            encoders_cfg=args.get("encoders") or {},
        )
