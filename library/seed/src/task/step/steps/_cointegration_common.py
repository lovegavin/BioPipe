"""Shared decoding for the 0.70 cointegration operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def pair_series(form, sample_dim: str, feature_dim: str, y_label: str, x_label: str, step: str):
    """Return finite y/x observations for a bivariate cointegration test."""
    frame = table_frame(form, sample_dim, feature_dim, step)
    y = numeric_column(frame, y_label, step)
    x = numeric_column(frame, x_label, step)
    valid = np.isfinite(y) & np.isfinite(x)
    y = y[valid]
    x = x[valid]
    if y.size < 10:
        raise StepError(f"{step}: need at least 10 complete observations")
    if np.var(y) == 0 or np.var(x) == 0:
        raise StepError(f"{step}: both series must vary")
    return y, x, int(y.size)


def variables_matrix(form, sample_dim: str, feature_dim: str, step: str):
    """Return complete observations and variable names for Johansen's test."""
    frame = table_frame(form, sample_dim, feature_dim, step)
    features = [name for name in frame.columns if name != "__sample__"]
    if len(features) < 2:
        raise StepError(f"{step}: need at least 2 variables")
    columns = [numeric_column(frame, name, step) for name in features]
    data = np.column_stack(columns)
    valid = np.isfinite(data).all(axis=1)
    data = data[valid]
    if data.shape[0] < 10:
        raise StepError(f"{step}: need at least 10 complete observations")
    if np.any(np.var(data, axis=0) == 0):
        raise StepError(f"{step}: every variable must vary")
    return data, features, int(data.shape[0])
