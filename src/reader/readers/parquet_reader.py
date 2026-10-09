# src/reader/readers/parquet_reader.py
"""Parquet reader.

Reads a Parquet file as a tabular dataset. Same column contract as the
CSV reader: every column enters data; non-numeric columns are encoded.

Positions in ``labels`` are 0-based indices within ``data``, i.e. they
refer directly to columns of the file, since nothing is stripped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder


class ParquetReader(Reader):
    """Reader for .parquet files."""

    extensions = [".parquet"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if not isinstance(dims, list) or not dims:
            raise ReaderError(
                "Parquet reader expects dims as a non-empty list of names, "
                "e.g. dims: [sample, field]"
            )

        encoders_cfg = args.get("encoders", {})

        df = pd.read_parquet(path)
        if df.shape[1] < 1:
            raise ReaderError("Parquet file has no columns")

        # Read Parquet file metadata and Arrow schema for info.
        meta = pq.read_metadata(str(path))
        schema = meta.schema

        parquet_metadata = {
            "num_rows": meta.num_rows,
            "num_columns": meta.num_columns,
            "num_row_groups": meta.num_row_groups,
            "created_by": meta.created_by,
            "format_version": meta.format_version,
        }

        arrow_schema = {}
        for i in range(len(schema)):
            col = schema.column(i)
            arrow_schema[col.name] = str(col.physical_type)

        # Map data column positions to label names.
        pos_to_label: dict[int, str] = {}
        for mapping in labels.values():
            for lab, pos in mapping.items():
                pos_to_label[pos] = lab

        cols = []
        dtypes = {}
        for col_idx in range(df.shape[1]):
            col = df.iloc[:, col_idx]
            col_name = str(df.columns[col_idx])
            dtypes[col_name] = str(col.dtype)

            if col.dtype != object:
                cols.append(col.to_numpy(dtype=np.float32))
                continue

            label_name = pos_to_label.get(col_idx)
            enc_name = (
                encoders_cfg.get(label_name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            cols.append(get_encoder(enc_name).fit_transform(col.tolist()))

        data = np.stack(cols, axis=1).astype(np.float32)

        return Form(
            data=data,
            dims=list(dims),
            labels={k: dict(v) for k, v in labels.items()},
            info={
                "missing_code": np.nan,
                "source_format": "parquet",
                "columns": [str(c) for c in df.columns],
                "dtypes": dtypes,
                "parquet_metadata": parquet_metadata,
                "arrow_schema": arrow_schema,
            },
        )