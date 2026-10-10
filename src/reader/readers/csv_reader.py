# src/reader/readers/csv_reader.py
"""CSV reader.

A two-dimensional, comma-separated table. The first line is treated
as a header by default; set ``header: false`` in args to read every
line as data.

Compression (.gz, .bz2, .xz) is handled by pandas directly; this
reader receives the original path.

Label rules accepted:

    builtin           header row (valid only for the column dim)
    auto              position indices "0", "1", ...
    {<col_dim>: <k>}  read column <k>; its values become the row
                      labels and the column is removed from data
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Non-numeric columns are encoded. The encoder instance used for each
column is recorded in ``info["encoders"]`` as
``{col_dim: {label: encoder}}``.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


class CsvReader(Reader):
    """Reader for .csv files."""

    extensions = [".csv"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"CSV reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        has_header = bool(args.get("header", True))
        encoders_cfg = args.get("encoders", {})

        df = pd.read_csv(path, header=0 if has_header else None)
        if has_header:
            col_names = [str(c) for c in df.columns]
        else:
            col_names = [str(i) for i in range(df.shape[1])]
        df.columns = col_names

        extracted: dict[str, dict[str, int]] = {}
        cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"CSV reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"CSV reader: 'builtin' is only valid for the "
                        f"column dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < df.shape[1]:
                        raise ReaderError(
                            f"CSV reader: labels.{row_dim} column "
                            f"index {k} out of range "
                            f"(file has {df.shape[1]} columns)"
                        )
                    cols_to_drop.add(k)
                    values = df.iloc[:, k].astype(str).tolist()
                    extracted[row_dim] = unique_labels(
                        values, row_dim, "csv"
                    )
                elif dim_name == row_dim:
                    extracted[row_dim] = {
                        str(k): int(v) for k, v in rule.items()
                    }
                elif dim_name == col_dim:
                    extracted[col_dim] = {
                        str(k): int(v) for k, v in rule.items()
                    }
                else:
                    raise ReaderError(
                        f"CSV reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"CSV reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        keep = [i for i in range(df.shape[1]) if i not in cols_to_drop]
        kept_names = [col_names[i] for i in keep]

        encoders_used: dict[str, object] = {}
        cols_data = []
        for old_idx in keep:
            col = df.iloc[:, old_idx]
            numeric = True
            try:
                values = col.to_numpy(dtype=np.float32)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols_data.append(values)
                continue

            name = col_names[old_idx]
            enc_name = (
                encoders_cfg.get(name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            encoder = get_encoder(enc_name)
            cols_data.append(encoder.fit_transform(col.tolist()))
            encoders_used[name] = encoder

        data = np.stack(cols_data, axis=1).astype(np.float32)

        final: dict[str, dict[str, int]] = {}

        if row_dim in extracted:
            final[row_dim] = extracted[row_dim]
        else:
            final[row_dim] = {
                str(i): i for i in range(data.shape[0])
            }

        if col_dim in extracted:
            final[col_dim] = extracted[col_dim]
        else:
            rule = labels.get(col_dim)
            if rule == "builtin":
                final[col_dim] = unique_labels(
                    kept_names, col_dim, "csv"
                )
            else:
                final[col_dim] = {
                    str(i): i for i in range(data.shape[1])
                }

        info: dict = {"missing_code": np.nan}
        if encoders_used:
            info["encoders"] = {col_dim: encoders_used}

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
        )