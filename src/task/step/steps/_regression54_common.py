"""Shared OLS helpers for the 0.54 regression diagnostics."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from ._ext_common import labels_in_order, reorder, require_dims


def regression_series(
    form,
    sample_dim: str,
    variable_dim: str,
    response: str,
    regressor: str,
    order_by: str | None,
    label: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return finite response/regressor/order arrays sorted by order."""
    require_dims(form, sample_dim, variable_dim, label=label)
    data = reorder(form, sample_dim, variable_dim)
    variables = labels_in_order(form, variable_dim)
    if response not in variables:
        raise StepError(f"{label}: response {response!r} not in {variables}")
    if regressor not in variables:
        raise StepError(f"{label}: regressor {regressor!r} not in {variables}")
    if response == regressor:
        raise StepError(f"{label}: response and regressor must be different")
    order_name = order_by or regressor
    if order_name not in variables:
        raise StepError(f"{label}: order column {order_name!r} not in {variables}")

    ri = variables.index(response)
    xi = variables.index(regressor)
    oi = variables.index(order_name)
    y = data[:, ri]
    x = data[:, xi]
    order = data[:, oi]
    mask = np.isfinite(y) & np.isfinite(x) & np.isfinite(order)
    if int(mask.sum()) < 4:
        raise StepError(f"{label}: at least four complete observations are required")
    y = y[mask]
    x = x[mask]
    order = order[mask]
    idx = np.argsort(order, kind="mergesort")
    return y[idx], x[idx], order[idx]


def ols_rss(x: np.ndarray, y: np.ndarray, label: str) -> float:
    """Residual sum of squares for y ~ 1 + x."""
    if x.size < 3:
        raise StepError(f"{label}: each segment needs at least three observations")
    design = np.column_stack((np.ones_like(x), x))
    if np.linalg.matrix_rank(design) < 2:
        raise StepError(f"{label}: regressor is constant")
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ beta
    return float(np.sum(residuals * residuals))


def gq_points(n: int, fraction: float, label: str) -> tuple[int, int]:
    """R lmtest::gqtest point indices with point=0.5."""
    if not 0.0 <= fraction < 0.5:
        raise StepError(f"{label}: fraction must be in [0, 0.5)")
    point1 = int(np.floor((0.5 - fraction / 2.0) * n))
    point2 = int(np.ceil((0.5 + fraction / 2.0) * n + 0.01))
    k = 2
    if point1 < k or point2 > n - k + 1 or point2 <= point1:
        raise StepError(
            f"{label}: too few observations in a segment for this fraction "
            f"(point1={point1}, point2={point2}, n={n})"
        )
    return point1, point2


def rainbow_slice(n: int, fraction: float, center: float, label: str) -> tuple[int, int]:
    """R lmtest::raintest subset indices (1-based inclusive)."""
    if not 0.0 < fraction < 1.0:
        raise StepError(f"{label}: fraction must be in (0, 1)")
    if not 0.0 < center < 1.0:
        raise StepError(f"{label}: center must be in (0, 1)")
    low = center - fraction / 2.0
    high = center + fraction / 2.0
    if low < 0.0 or high > 1.0:
        raise StepError(f"{label}: center +/- fraction/2 must stay inside [0, 1]")
    from_ = int(np.ceil(float(np.quantile(np.arange(1, n + 1), low, method="linear"))))
    to = from_ + int(np.floor(fraction * n)) - 1
    if from_ < 1 or to > n or to <= from_:
        raise StepError(f"{label}: invalid central subset for this fraction")
    return from_, to
