"""JSON table reader."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.reader.base import Reader
from ._table_common import table_form


class JsonTableReader(Reader):
    provider = 'operon-readers'
    """Reader for a JSON array of records or a mapping of column -> list."""
    parameters_file = 'json_table_reader.JsonTableReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'JsonTableReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for a JSON array of records or a mapping of column -> list',
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
     'description': 'Reader for a JSON array of records or a mapping of column -> list.',
     'extensions': ['.json'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReaderError(f"JSON table reader: cannot parse {path}: {exc}") from exc
        try:
            df = pd.DataFrame(payload)
            if args.get("orient", "records") == "columns":
                df = pd.DataFrame(payload)
        except (ValueError, TypeError) as exc:
            raise ReaderError(f"JSON table reader: unsupported JSON table shape: {exc}") from exc
        if df.ndim != 2:
            raise ReaderError("JSON table reader: JSON must describe a two-dimensional table")
        return table_form(df, dims, labels, "JSON", args.get("encoders", {}))
