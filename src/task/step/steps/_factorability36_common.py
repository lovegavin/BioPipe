"""Shared correlation-matrix helpers for factorability diagnostics."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def correlation_matrix(
    form,
    sample_dim: str,
    feature_dim: str,
    label: str,
):
    """Return (correlation matrix, variable names, sample count)."""
    frame = table_frame(form, sample_dim, feature_dim, label)
    names = [name for name in frame.columns if name != "__sample__"]
    if len(names) < 2:
        raise StepError(f"{label}: at least two variables are required")
    matrix = np.column_stack(
        [numeric_column(frame, name, label) for name in names]
    ).astype(np.float64, copy=False)
    keep = np.isfinite(matrix).all(axis=1)
    matrix = matrix[keep]
    n, p = matrix.shape
    if n <= p:
        raise StepError(f"{label}: need more complete samples than variables")
    if np.any(np.var(matrix, axis=0, ddof=1) <= 0):
        raise StepError(f"{label}: every variable must have positive variance")
    correlation = np.corrcoef(matrix, rowvar=False)
    if not np.isfinite(correlation).all():
        raise StepError(f"{label}: correlation matrix is not finite")
    if np.linalg.matrix_rank(correlation) < p:
        raise StepError(f"{label}: correlation matrix is singular")
    return correlation, names, n
