"""Zarr array reader (2-D numeric arrays)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class ZarrReader(Reader):
    """Read a two-dimensional numeric Zarr array or group member."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "builtin"}}
    extensions = [".zarr"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "array": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"Zarr reader requires exactly two dims, got {dims}")
        try:
            import zarr
        except ImportError as exc:
            raise ReaderError("Zarr reader: zarr is required") from exc
        try:
            obj = zarr.open(str(path), mode="r")
        except Exception as exc:
            raise ReaderError(f"Zarr reader: cannot open {path}: {exc}") from exc
        key = args.get("array")
        if hasattr(obj, "shape"):
            array = obj
        else:
            keys = list(obj.array_keys())
            if key is None:
                if len(keys) != 1:
                    raise ReaderError(
                        f"Zarr reader: group has {len(keys)} arrays; pass 'array' to choose one"
                    )
                key = keys[0]
            if key not in keys:
                raise ReaderError(f"Zarr reader: array {key!r} not found in {keys}")
            array = obj[key]
        try:
            data = np.asarray(array[:], dtype=np.float64)
        except Exception as exc:
            raise ReaderError(f"Zarr reader: cannot read array: {exc}") from exc
        if data.ndim != 2:
            raise ReaderError(f"Zarr reader: expected a 2D array, got shape {data.shape}")
        row_values = list(array.attrs.get("rows", range(data.shape[0])))
        col_values = list(array.attrs.get("columns", range(data.shape[1])))
        final = {
            dims[0]: unique_labels([str(v) for v in row_values], dims[0], "Zarr"),
            dims[1]: unique_labels([str(v) for v in col_values], dims[1], "Zarr"),
        }
        if len(final[dims[0]]) != data.shape[0] or len(final[dims[1]]) != data.shape[1]:
            raise ReaderError("Zarr reader: row/column labels do not match the array shape")
        return Form(
            data=compact_numeric(data), dims=list(dims), labels=final,
            info={"format": "Zarr", "missing_code": np.nan, "array": key or "/"},
        )
