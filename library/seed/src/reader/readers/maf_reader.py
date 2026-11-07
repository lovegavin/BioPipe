"""Mutation Annotation Format (MAF) reader.

Reads the tab-separated MAF table used by TCGA/GDC. Comment and version
lines beginning with ``#`` are skipped; the first remaining line is the
header. All columns are retained and returned as variant x field.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class MafReader(Reader):
    provider = 'operon-readers'
    """Mutation Annotation Format table reader."""
    parameters_file = 'maf_reader.MafReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'MafReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Mutation Annotation Format table reader',
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
     'description': 'Mutation Annotation Format table reader.',
     'extensions': ['.maf'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['variant', 'field'], 'labels': {'variant': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"maf reader requires exactly two dims, got {dims}")
        try:
            df = pd.read_csv(path, sep="\t", comment="#", dtype=str, low_memory=False)
        except Exception as exc:
            raise ReaderError(f"maf reader: cannot parse {path}: {exc}") from exc
        if df.shape[0] == 0 or df.shape[1] == 0:
            raise ReaderError("maf reader: table has zero rows or columns")
        df.columns = [str(c).strip() for c in df.columns]
        return table_form(
            df, dims, labels, "maf",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"variant:{i}" for i in range(df.shape[0])],
        )
