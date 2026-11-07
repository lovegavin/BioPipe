"""BEDPE reader.

Reads the 10 standard BEDPE columns. Browser and track
comment lines are ignored. Coordinates are zero-based, half-open."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BedpeReader(Reader):
    provider = 'operon-readers'
    """Paired-end BED reader."""
    parameters_file = 'bedpe_reader.BedpeReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BedpeReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Paired-end BED reader',
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
     'description': 'Paired-end BED reader.',
     'extensions': ['.bedpe'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BEDPE reader requires exactly two dims, got {dims}")
        df = df = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
        if df.shape[1] != 10:
            raise ReaderError(f"BEDPE reader: expected 10 columns, got {df.shape[1]}")
        df.columns = ["chrom1", "start1", "end1", "chrom2", "start2", "end2",
                      "name", "score", "strand1", "strand2"]
        return table_form(
            df, dims, labels, "BEDPE",
            encoders_cfg=args.get("encoders") or {},
        )
