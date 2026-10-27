# src/reader/readers/csv_reader.py
"""CSV reader.

Comma-separated (or custom-separator) two-dimensional tables. The
first line is treated as a header by default; set ``header: false``
in args to read every line as data.

Compression (.gz, .bz2, .xz) is handled by pandas directly; this
reader receives the original path.

Label rules accepted:

    builtin           header row (valid only for the column dim)
    auto              position indices "0", "1", ...
    {<col_dim>: <k>}  read column <k>; its values become the row
                      labels and the column is removed from data.
                      ``k`` is a position in the original file,
                      independent of ``columns``.
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Column selection
----------------
``columns`` restricts the reader to a subset of header names, in the
order given. ``labels`` indices still refer to the original file.

Info columns
------------
``info_columns`` maps a header name to an info field name. The column
is read verbatim as strings into ``info[field]`` and declared parallel
to the row dimension in ``axis_info``. The column is removed from
data.

Non-numeric columns are encoded. The encoder instance used for each
column is recorded in ``info["encoders"]`` as
``{col_dim: {label: encoder}}``.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
    <info_columns>    one entry per declared info column
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.core.contracts import reader_contract
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels
from src.core.numeric import compact_numeric


class CsvReader(Reader):
    """Reader for .csv files."""

    output_contract = reader_contract()

    file_input = {
        "dims": ["sample", "feature"],
        "labels": {"sample": "auto", "feature": "builtin"},
        "compression": [".gz", ".bz2", ".xz"],
    }

    extensions = [".csv"]
    default_sep = ","
    format_name = "CSV"
    handles_compression = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "header": {
                "type": "boolean",
                "title": "Header row",
                "default": True,
            },
            "sep": {
                "type": "string",
                "title": "Separator",
                "minLength": 1,
            },
            "encoders": {
                "type": "object",
                "title": "Encoders",
                "additionalProperties": True,
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "title": "Columns",
            },
            "info_columns": {
                "type": "object",
                "title": "Info columns",
                "additionalProperties": {"type": "string"},
            },
        },
        "additionalProperties": True,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"{self.format_name} reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        has_header = bool(args.get("header", True))

        sep = args.get("sep", self.default_sep)
        if not isinstance(sep, str) or not sep:
            raise ReaderError(
                f"{self.format_name} reader: 'sep' must be a non-empty string, got {sep!r}"
            )

        encoders_cfg = args.get("encoders", {})
        if not isinstance(encoders_cfg, dict):
            raise ReaderError(f"{self.format_name} reader: 'encoders' must be a mapping")

        columns_cfg = args.get("columns")
        if columns_cfg is not None:
            if (not isinstance(columns_cfg, list)
                    or not columns_cfg
                    or any(not isinstance(c, str) or not c
                           for c in columns_cfg)):
                raise ReaderError(
                    f"{self.format_name} reader: 'columns' must be a non-empty list of "
                    "header names"
                )
            if len(set(columns_cfg)) != len(columns_cfg):
                raise ReaderError(
                    f"{self.format_name} reader: 'columns' contains duplicates"
                )

        info_columns_cfg = args.get("info_columns", {})
        if not isinstance(info_columns_cfg, dict):
            raise ReaderError(
                f"{self.format_name} reader: 'info_columns' must be a mapping of "
                "column name -> info field name"
            )
        for col_name, info_key in info_columns_cfg.items():
            if not isinstance(col_name, str) or not col_name:
                raise ReaderError(
                    f"{self.format_name} reader: info_columns key must be a non-empty "
                    f"string, got {col_name!r}"
                )
            if not isinstance(info_key, str) or not info_key:
                raise ReaderError(
                    f"{self.format_name} reader: info_columns['{col_name}'] must be a "
                    f"non-empty string, got {info_key!r}"
                )

        df = pd.read_csv(path, header=0 if has_header else None, sep=sep)
        if df.shape[0] == 0:
            raise ReaderError(
                f"{self.format_name} reader: file has zero data rows: {path}"
            )

        if has_header:
            col_names = [str(c) for c in df.columns]
        else:
            col_names = [str(i) for i in range(df.shape[1])]
        df.columns = col_names

        if len(set(col_names)) != len(col_names):
            raise ReaderError(
                f"{self.format_name} reader: header contains duplicate column names; "
                "rename them before reading"
            )

        if columns_cfg is not None:
            missing = [c for c in columns_cfg if c not in col_names]
            if missing:
                raise ReaderError(
                    f"{self.format_name} reader: requested columns not in header: "
                    f"{missing}. Available: {col_names}"
                )
        for col_name in info_columns_cfg:
            if col_name not in col_names:
                raise ReaderError(
                    f"{self.format_name} reader: info_columns key '{col_name}' not in "
                    f"header. Available: {col_names}"
                )

        extracted: dict[str, dict[str, int]] = {}
        label_cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"{self.format_name} reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"{self.format_name} reader: 'builtin' is only valid for the "
                        f"column dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < df.shape[1]:
                        raise ReaderError(
                            f"{self.format_name} reader: labels.{row_dim} column "
                            f"index {k} out of range "
                            f"(file has {df.shape[1]} columns)"
                        )
                    label_cols_to_drop.add(k)
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
                        f"{self.format_name} reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"{self.format_name} reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        info_extracted: dict[str, list[str]] = {}
        info_cols_to_drop: set[int] = set()
        for col_name, info_key in info_columns_cfg.items():
            idx = col_names.index(col_name)
            if idx in label_cols_to_drop:
                raise ReaderError(
                    f"{self.format_name} reader: column '{col_name}' is already "
                    f"consumed as a label column; cannot also declare "
                    f"it as an info column"
                )
            if info_key in info_extracted:
                raise ReaderError(
                    f"{self.format_name} reader: info field '{info_key}' is declared "
                    f"twice in info_columns"
                )
            info_extracted[info_key] = (
                df.iloc[:, idx].fillna("").astype(str).tolist()
            )
            info_cols_to_drop.add(idx)

        if columns_cfg is not None:
            selected_indices = [col_names.index(c) for c in columns_cfg]
            df = df.iloc[:, selected_indices]
            new_col_names = [col_names[i] for i in selected_indices]
            old_to_new = {
                old: new for new, old in enumerate(selected_indices)
            }
            label_cols_to_drop = {
                old_to_new[i] for i in label_cols_to_drop
                if i in old_to_new
            }
            info_cols_to_drop = {
                old_to_new[i] for i in info_cols_to_drop
                if i in old_to_new
            }
            col_names = new_col_names

        keep = [
            i for i in range(df.shape[1])
            if i not in label_cols_to_drop
            and i not in info_cols_to_drop
        ]
        if not keep:
            raise ReaderError(
                f"{self.format_name} reader: no data columns remain after label and "
                "info column extraction"
            )
        kept_names = [col_names[i] for i in keep]

        encoders_used: dict[str, object] = {}
        cols_data = []
        for old_idx in keep:
            col = df.iloc[:, old_idx]
            numeric = True
            try:
                values = col.to_numpy(dtype=np.float64)
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

        data = compact_numeric(np.stack(cols_data, axis=1))

        final: dict[str, dict[str, int]] = {}

        if row_dim in extracted:
            final[row_dim] = extracted[row_dim]
        else:
            final[row_dim] = {str(i): i for i in range(data.shape[0])}

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
        info.update(info_extracted)
        if encoders_used:
            info["encoders"] = {col_dim: encoders_used}

        axis_info: dict[str, list[str]] = {}
        if info_extracted:
            axis_info[row_dim] = list(info_extracted.keys())

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
            axis_info=axis_info,
        )