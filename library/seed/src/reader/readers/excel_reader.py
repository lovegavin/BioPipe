"""Excel workbook reader using pandas/openpyxl."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.reader.base import Reader
from ._table_common import table_form


class ExcelReader(Reader):
    provider = 'operon-readers'
    """Reader for .xlsx and .xlsm workbooks."""
    parameters_file = 'excel_reader.ExcelReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ExcelReader',
     'version': '1.0.0',
     'kind': 'reader',
     'dependencies': ['openpyxl>=3.1'],
     'dependency_imports': ['openpyxl'],
     'title': 'Reader for .xlsx and .xlsm workbooks',
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
     'description': 'Reader for .xlsx and .xlsm workbooks.',
     'extensions': ['.xlsx', '.xlsm'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        return self._read(path, dims, labels, **args)

    def _read(self, path, dims, labels, **args):
        try:
            df = pd.read_excel(
                path,
                sheet_name=args.get("sheet", 0),
                header=0 if args.get("header", True) else None,
                engine="openpyxl",
            )
        except Exception as exc:
            raise ReaderError(f"Excel reader: cannot read {path}: {exc}") from exc
        if not args.get("header", True):
            df.columns = [str(i) for i in range(df.shape[1])]
        return table_form(
            df, dims, labels, "Excel", args.get("encoders", {}),
            row_labels=list(range(df.shape[0])) if args.get("header", True) else None,
        )
