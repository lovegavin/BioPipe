"""Shared OLS setup for the 0.29 regression diagnostics."""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm

from src.core import StepError

from ._stats21_common import design_matrix, numeric_column, table_frame


def fit_linear(
    form,
    sample_dim: str,
    feature_dim: str,
    response_label: str,
    predictors: list[str],
    categorical: list[str],
    label: str,
):
    """Fit an intercept OLS model after dropping non-finite rows."""
    frame = table_frame(form, sample_dim, feature_dim, label)
    y = numeric_column(frame, response_label, label)
    X, names = design_matrix(frame, predictors, categorical, label)
    keep = np.isfinite(y) & np.isfinite(X).all(axis=1)
    X = X[keep]
    y = y[keep]
    if y.size <= X.shape[1] + 2:
        raise StepError(f"{label}: not enough observations for the regression")
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise StepError(f"{label}: design matrix is rank deficient after filtering")
    result = sm.OLS(y, X).fit()
    return result, X, y, names


def validate_lags(lags: int, n: int, k: int, label: str) -> None:
    if lags < 1:
        raise StepError(f"{label}: lags must be at least 1")
    if lags >= n - k:
        raise StepError(f"{label}: lags must be smaller than residual degrees of freedom")
