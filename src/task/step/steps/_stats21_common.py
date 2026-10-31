"""Shared table decoding for the 0.21 regression operators."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import StepError


def ordered_labels(form, dim: str) -> list[str]:
    return [name for name, _ in sorted(form.labels[dim].items(), key=lambda item: item[1])]


def table_frame(form, sample_dim: str, feature_dim: str, label: str) -> pd.DataFrame:
    """Return a sample-indexed DataFrame with decoded feature columns."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: input must be 2D")
    if sample_dim not in form.dims or feature_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {sample_dim!r}, {feature_dim!r}, got {form.dims}"
        )
    data = np.asarray(form.data)
    if form.dims.index(sample_dim) == 1:
        data = data.T
    samples = ordered_labels(form, sample_dim)
    if data.shape[0] != len(samples):
        raise StepError(f"{label}: sample labels do not match data rows")
    features = ordered_labels(form, feature_dim)
    encoders = form.info.get("encoders", {}).get(feature_dim, {})
    columns: dict[str, np.ndarray] = {}
    for j, name in enumerate(features):
        raw = data[:, j]
        enc = encoders.get(name)
        if enc is not None and hasattr(enc, "inverse"):
            values = []
            for value in raw:
                try:
                    key = int(round(float(value)))
                except (TypeError, ValueError):
                    values.append(None)
                    continue
                values.append(enc.inverse.get(key, None))
            columns[name] = np.asarray(values, dtype=object)
        else:
            columns[name] = raw
    frame = pd.DataFrame(columns)
    frame.insert(0, "__sample__", samples)
    return frame


def numeric_column(frame: pd.DataFrame, name: str, label: str) -> np.ndarray:
    if name not in frame.columns:
        raise StepError(f"{label}: column {name!r} not found")
    try:
        values = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise StepError(f"{label}: column {name!r} is not numeric") from exc
    return values


def design_matrix(
    frame: pd.DataFrame,
    predictors: list[str],
    categorical: list[str],
    label: str,
):
    """Build an intercept + predictor matrix and return (matrix, term names)."""
    if not predictors:
        raise StepError(f"{label}: predictors must be a non-empty list")
    parts = []
    names = ["Intercept"]
    parts.append(np.ones((len(frame), 1), dtype=np.float64))
    for name in predictors:
        if name not in frame.columns:
            raise StepError(f"{label}: predictor {name!r} not found")
        if name in categorical:
            values = frame[name].astype(str)
            dummies = pd.get_dummies(values, prefix=name, drop_first=True, dtype=float)
            if dummies.shape[1] == 0:
                raise StepError(f"{label}: categorical {name!r} has only one level")
            parts.append(dummies.to_numpy(dtype=np.float64))
            names.extend(list(dummies.columns))
        else:
            values = numeric_column(frame, name, label)
            parts.append(values.reshape(-1, 1))
            names.append(name)
    matrix = np.column_stack(parts)
    if matrix.shape[1] < 2:
        raise StepError(f"{label}: design matrix has no predictors")
    if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise StepError(f"{label}: design matrix is rank deficient")
    return matrix, names
