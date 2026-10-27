# src/reader/readers/loom_reader.py
"""Loom reader for single-cell matrices.

A Loom file is HDF5. The default matrix is ``/matrix`` with shape
(genes, cells); row identifiers live in ``/row_attrs/GeneIDs`` and
column identifiers in ``/col_attrs/CellID``. Common alternatives
(``Gene``/``GeneIDs`` and ``CellID``/``CellIDs``) are accepted.

The reader keeps the matrix dense (Loom matrices are normally dense)
and preserves the first-axis/second-axis order from the manifest.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels

_ROW_KEYS = ("GeneIDs", "Gene", "gene_ids", "genes", "_index")
_COL_KEYS = ("CellID", "CellIDs", "cell_ids", "cells", "_index")


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class LoomReader(Reader):
    """Reader for .loom files."""

    output_contract = reader_contract()
    dependencies = ["h5py>=3.9"]
    dependency_imports = ["h5py"]

    file_input = {
        "dims": ["gene", "cell"],
        "labels": {"gene": "builtin", "cell": "builtin"},
    }
    extensions = [".loom"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "matrix": {"type": "string", "default": "matrix"},
            "row_ids": {"type": "string"},
            "col_ids": {"type": "string"},
        },
        "additionalProperties": False,
    }

    @staticmethod
    def _ids(group, keys):
        import h5py
        for key in keys:
            if key not in group:
                continue
            value = group[key]
            if isinstance(value, h5py.Dataset):
                return [_text(v) for v in value[:]]
        return None

    def _matrix(self, path: Path, args):
        import h5py
        with h5py.File(path, "r") as handle:
            key = str(args.get("matrix", "matrix")).lstrip("/")
            if key not in handle:
                raise ReaderError(f"Loom matrix /{key} does not exist")
            matrix = handle[key]
            if not hasattr(matrix, "shape") or len(matrix.shape) != 2:
                raise ReaderError("Loom matrix must be a two-dimensional dataset")
            row_ids = None
            col_ids = None
            if "row_attrs" in handle:
                custom = args.get("row_ids")
                row_ids = self._ids(handle["row_attrs"], (custom,) if custom else _ROW_KEYS)
            if "col_attrs" in handle:
                custom = args.get("col_ids")
                col_ids = self._ids(handle["col_attrs"], (custom,) if custom else _COL_KEYS)
            return np.asarray(matrix[:], dtype=np.float32), row_ids, col_ids

    def probe(self, path, **args):
        import h5py
        with h5py.File(path, "r") as handle:
            key = str(args.get("matrix", "matrix")).lstrip("/")
            if key not in handle:
                raise ReaderError(f"Loom matrix /{key} does not exist")
            shape = tuple(int(n) for n in handle[key].shape)
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": shape,
            "dtype": "float32",
            "dense_bytes": shape[0] * shape[1] * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"Loom reader requires exactly two dims, got {dims}")
        data, row_ids, col_ids = self._matrix(path, args)
        n_rows, n_cols = data.shape
        row_ids = row_ids or [str(i) for i in range(n_rows)]
        col_ids = col_ids or [str(i) for i in range(n_cols)]
        if len(row_ids) != n_rows or len(col_ids) != n_cols:
            raise ReaderError("Loom axis identifiers do not match matrix shape")

        def resolve(dim: str, builtin: list[str]):
            rule = labels.get(dim, "builtin")
            if rule in (None, "builtin"):
                return unique_labels(builtin, dim, "loom")
            if rule == "auto":
                return {str(i): i for i in range(len(builtin))}
            if isinstance(rule, dict):
                return {str(k): int(v) for k, v in rule.items()}
            raise ReaderError(f"Loom reader: unsupported label rule for {dim!r}: {rule!r}")

        form = Form(
            data=data,
            dims=list(dims),
            labels={
                dims[0]: resolve(dims[0], row_ids),
                dims[1]: resolve(dims[1], col_ids),
            },
            info={"missing_code": np.nan},
        )
        form.validate()
        return form
