# src/reader/readers/csv_reader.py
"""CSV reader.

Empty fields are read as NaN for numeric columns. In a string column,
an empty field is treated as a distinct label and encoded like any
other value.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader


class _LabelEncoder:
    def fit_transform(self, values) -> np.ndarray:
        order = list(dict.fromkeys(values))
        mapping = {v: i for i, v in enumerate(order)}
        return np.asarray([mapping[v] for v in values], dtype=np.float32)


_ENCODERS = {"labelencoder": _LabelEncoder}


def _get_encoder(name: str):
    if name not in _ENCODERS:
        raise ReaderError(
            f"Unknown encoder '{name}'. Available: {sorted(_ENCODERS)}"
        )
    return _ENCODERS[name]()


class CsvReader(Reader):
    """Reader for .csv files."""

    extensions = [".csv"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if not isinstance(dims, list) or not dims:
            raise ReaderError("dims must be a non-empty list of names")

        encoders_cfg = args.get("encoders", {})
        df = pd.read_csv(path, header=None)

        pos_to_label: dict[int, str] = {}
        for mapping in labels.values():
            for lab, pos in mapping.items():
                pos_to_label[pos] = lab

        cols = []
        for col_idx in range(df.shape[1]):
            col = df.iloc[:, col_idx]

            if col.dtype != object:
                # numeric column; empty cells are already NaN
                cols.append(col.to_numpy(dtype=np.float32))
                continue

            # string column; NaN counts as its own label
            label_name = pos_to_label.get(col_idx)
            enc_name = (
                encoders_cfg.get(label_name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            cols.append(_get_encoder(enc_name).fit_transform(col.tolist()))

        data = np.stack(cols, axis=1).astype(np.float32)

        return Form(
            data=data,
            dims=list(dims),
            labels={k: dict(v) for k, v in labels.items()},
            info={"missing_code": np.nan, "source_format": "csv"},
        )