"""Shared helpers for the additional table-like readers."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


def labels_for(values, dim: str, rule, format_name: str) -> dict:
    values = [str(v) for v in values]
    if rule in (None, "auto", "builtin"):
        return unique_labels(values, dim, format_name)
    if isinstance(rule, dict):
        out = {}
        for key, pos in rule.items():
            if not isinstance(pos, int) or not 0 <= pos < len(values):
                raise ReaderError(
                    f"{format_name} reader: labels.{dim} position {pos!r} is invalid"
                )
            out[str(key)] = pos
        if len(set(out.values())) != len(out):
            raise ReaderError(f"{format_name} reader: labels.{dim} has duplicate positions")
        return out
    raise ReaderError(
        f"{format_name} reader: labels.{dim} must be 'builtin', 'auto', a mapping, or omitted; got {rule!r}"
    )


def encode_frame(df: pd.DataFrame, encoders_cfg: dict, format_name: str):
    if df.shape[0] == 0 or df.shape[1] == 0:
        raise ReaderError(f"{format_name} reader: table has zero rows or columns")
    cols = [str(c) for c in df.columns]
    if len(set(cols)) != len(cols):
        raise ReaderError(f"{format_name} reader: duplicate column names")
    df = df.copy()
    df.columns = cols
    arrays = []
    encoders = {}
    for col in cols:
        series = df[col]
        try:
            values = series.to_numpy(dtype=np.float64)
            if not np.isfinite(values).any():
                raise ValueError
            arrays.append(values)
            continue
        except (ValueError, TypeError):
            pass
        name = str(encoders_cfg.get(col) or encoders_cfg.get("all") or "labelencoder")
        encoder = get_encoder(name)
        arrays.append(encoder.fit_transform(series.fillna("").astype(str).tolist()))
        encoders[col] = encoder
    return np.stack(arrays, axis=1), cols, encoders


def table_form(df, dims, labels, format_name, encoders_cfg=None, row_labels=None,
               col_labels=None, info_extra=None):
    if len(dims) != 2:
        raise ReaderError(f"{format_name} reader requires exactly two dims, got {dims}")
    row_dim, col_dim = dims[0], dims[1]
    if not isinstance(encoders_cfg, dict):
        raise ReaderError(f"{format_name} reader: 'encoders' must be a mapping")
    data, cols, encoders = encode_frame(df, encoders_cfg or {}, format_name)
    row_values = row_labels if row_labels is not None else list(range(data.shape[0]))
    col_values = col_labels if col_labels is not None else cols
    final = {
        row_dim: labels_for(row_values, row_dim, labels.get(row_dim), format_name),
        col_dim: labels_for(col_values, col_dim, labels.get(col_dim), format_name),
    }
    if len(final[row_dim]) != data.shape[0]:
        raise ReaderError(f"{format_name} reader: row label count does not match data")
    if len(final[col_dim]) != data.shape[1]:
        raise ReaderError(f"{format_name} reader: column label count does not match data")
    info = {"missing_code": np.nan}
    if encoders:
        info["encoders"] = {col_dim: encoders}
    if info_extra:
        info.update(info_extra)
    return Form(data=compact_numeric(data), dims=list(dims), labels=final, info=info)


def read_whitespace(path: Path, names, format_name: str):
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
    except Exception as exc:
        raise ReaderError(f"{format_name} reader: cannot parse {path}: {exc}") from exc
    if df.shape[1] != len(names):
        raise ReaderError(
            f"{format_name} reader: expected {len(names)} columns, got {df.shape[1]}"
        )
    df.columns = names
    return df
