"""Shared matrix helpers for multivariate reliability operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def frame_matrix(
    form,
    sample_dim: str,
    feature_dim: str,
    label: str,
    columns: list[str] | None = None,
):
    """Decode a table into sample labels and a numeric matrix."""
    frame = table_frame(form, sample_dim, feature_dim, label)
    if columns:
        missing = [name for name in columns if name not in frame.columns]
        if missing:
            raise StepError(f"{label}: columns not found: {missing}")
        names = [str(name) for name in columns]
    else:
        names = [name for name in frame.columns if name != "__sample__"]
    if len(names) < 1:
        raise StepError(f"{label}: at least one feature column is required")
    matrix = np.column_stack(
        [numeric_column(frame, name, label) for name in names]
    )
    samples = [str(value) for value in frame["__sample__"].tolist()]
    return samples, names, matrix.astype(np.float64, copy=False)


def aligned_matrices(
    form_a,
    form_b,
    sample_dim: str,
    feature_a: str,
    feature_b: str,
    label: str,
):
    """Align two tables on common sample names and drop incomplete rows."""
    samples_a, names_a, matrix_a = frame_matrix(
        form_a, sample_dim, feature_a, label
    )
    samples_b, names_b, matrix_b = frame_matrix(
        form_b, sample_dim, feature_b, label
    )
    b_map = {name: index for index, name in enumerate(samples_b)}
    keep = [index for index, name in enumerate(samples_a) if name in b_map]
    if len(keep) < 3:
        raise StepError(f"{label}: fewer than three shared samples")
    X = matrix_a[keep]
    Y = matrix_b[[b_map[samples_a[index]] for index in keep]]
    valid = np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1)
    X = X[valid]
    Y = Y[valid]
    if X.shape[0] < 3:
        raise StepError(f"{label}: fewer than three finite shared samples")
    if X.shape[1] > X.shape[0] or Y.shape[1] > Y.shape[0]:
        raise StepError(f"{label}: fewer samples than variables")
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise StepError(f"{label}: first matrix is rank deficient")
    if np.linalg.matrix_rank(Y) < Y.shape[1]:
        raise StepError(f"{label}: second matrix is rank deficient")
    return names_a, names_b, X, Y
