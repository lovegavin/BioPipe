# src/reader/readers/csv_reader.py
"""CSV reader.

Reads every column of the CSV into data. No column is treated
specially. Non-numeric columns are encoded using the configured
encoder.

Positions in labels are 0-based indices within data, i.e. they refer
directly to columns of the file, since nothing is stripped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder


class CsvReader(Reader):
    """Reader for .csv files."""

    extensions = [".csv"]

    def read(
        self,
        path: Path,
        dims: list,
        labels: dict,
        **args,
    ) -> Form:
        if not isinstance(dims, list) or not dims:
            raise ReaderError(
                "CSV reader expects dims as a non-empty list of names, "
                "e.g. dims: [sample, field]"
            )

        encoders_cfg = args.get("encoders", {})
        df = pd.read_csv(path, header=None)

        # Map data column positions to label names.
        pos_to_label: dict[int, str] = {}
        for mapping in labels.values():
            for lab, pos in mapping.items():
                pos_to_label[pos] = lab

        cols = []
        dtypes = {}
        for col_idx in range(df.shape[1]):
            col = df.iloc[:, col_idx]
            col_name = str(col_idx)
            dtypes[col_name] = str(col.dtype)

            numeric = True
            try:
                values = col.to_numpy(dtype=np.float32)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols.append(values)
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
                "source_format": "csv",
                "columns": [str(c) for c in range(df.shape[1])],
                "dtypes": dtypes,
                "n_rows": int(df.shape[0]),
                "n_cols": int(df.shape[1]),
            },
        )