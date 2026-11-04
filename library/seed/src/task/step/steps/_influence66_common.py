"""Shared OLS influence helpers for the 0.66 regression diagnostics."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from ._ext_common import labels_in_order, reorder, require_dims


def influence_ols(form, sample_dim: str, feature_dim: str, response: str, label: str):
    """Fit y ~ 1 + X and return leave-one-out influence ingredients."""
    require_dims(form, sample_dim, feature_dim, label=label)
    data = np.asarray(reorder(form, sample_dim, feature_dim), dtype=np.float64)
    variables = labels_in_order(form, feature_dim)
    if response not in variables:
        raise StepError(f"{label}: response {response!r} not in {variables}")
    predictors = [name for name in variables if name != response]
    if not predictors:
        raise StepError(f"{label}: at least one predictor is required besides {response!r}")

    samples = labels_in_order(form, sample_dim)
    mask = np.isfinite(data).all(axis=1)
    if int(mask.sum()) < 4:
        raise StepError(f"{label}: at least four complete observations are required")
    data = data[mask]
    samples = [sample for sample, keep in zip(samples, mask) if keep]

    response_index = variables.index(response)
    predictor_indices = [variables.index(name) for name in predictors]
    y = data[:, response_index]
    design = np.column_stack((np.ones(data.shape[0]), data[:, predictor_indices]))
    n, p = design.shape
    if n <= p + 1:
        raise StepError(f"{label}: need more than {p + 1} complete observations for influence statistics")
    if np.linalg.matrix_rank(design) < p:
        raise StepError(f"{label}: design matrix is rank deficient")

    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coefficients
    sse = float(np.sum(residuals * residuals))
    mse = sse / (n - p)
    if mse <= 0:
        raise StepError(f"{label}: residuals have zero variance")

    xtx_inverse = np.linalg.inv(design.T @ design)
    leverage = np.sum((design @ xtx_inverse) * design, axis=1)
    if np.any(leverage >= 1.0 - 1e-12):
        raise StepError(f"{label}: a fitted point has leverage too close to one")
    s2_i = (sse - residuals * residuals / (1.0 - leverage)) / (n - p - 1)
    if np.any(s2_i <= 0):
        raise StepError(f"{label}: leave-one-out residual variance is not positive")
    return samples, predictors, y, design, residuals, leverage, mse, s2_i, p
