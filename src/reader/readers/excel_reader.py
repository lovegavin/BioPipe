"""Excel workbook reader using pandas/openpyxl."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


class ExcelReader(Reader):
    """Reader for .xlsx and .xlsm workbooks."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "builtin"}}
    extensions = [".xlsx", ".xlsm"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "sheet": {"type": ["string", "integer"], "default": 0},
            "header": {"type": "boolean", "default": True},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

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
