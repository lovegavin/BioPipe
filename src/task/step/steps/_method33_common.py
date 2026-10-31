"""Shared helpers for 0.33 method-comparison regressions."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from ._agreement32_common import paired_columns


def passing_bablok(x: np.ndarray, y: np.ndarray):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if np.any(x < 0) or np.any(y < 0):
        raise StepError("passing_bablok: method values must be non-negative")
    slopes = []
    for i in range(x.size - 1):
        dx = x[i + 1:] - x[i]
        dy = y[i + 1:] - y[i]
        keep = dx != 0
        slopes.extend((dy[keep] / dx[keep]).tolist())
    if not slopes:
        raise StepError("passing_bablok: no usable pairs with distinct method_a values")
    slope = float(np.median(slopes))
    intercept = float(np.median(y - slope * x))
    return slope, intercept, int(x.size)


def deming(x: np.ndarray, y: np.ndarray, error_ratio: float):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 3:
        raise StepError("deming_regression: need at least three complete pairs")
    if not np.isfinite(error_ratio) or error_ratio <= 0:
        raise StepError("deming_regression: error_ratio must be positive")
    sxx = float(np.var(x, ddof=1))
    syy = float(np.var(y, ddof=1))
    sxy = float(np.cov(x, y, ddof=1)[0, 1])
    if sxx == 0 or syy == 0:
        raise StepError("deming_regression: both methods must vary")
    if abs(sxy) < 1e-15:
        raise StepError("deming_regression: covariance is zero")
    delta = syy - error_ratio * sxx
    slope = (delta + np.sqrt(delta * delta + 4.0 * error_ratio * sxy * sxy)) / (2.0 * sxy)
    intercept = float(np.mean(y) - slope * np.mean(x))
    return float(slope), intercept, int(x.size)


def method_pairs(form, sample_dim: str, feature_dim: str, method_a: str, method_b: str, label: str):
    return paired_columns(form, sample_dim, feature_dim, method_a, method_b, label)
