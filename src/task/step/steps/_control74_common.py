"""Shared helpers for 0.74 control-chart operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def single_series(
    form,
    sample_dim: str,
    feature_dim: str,
    value_label: str,
    step: str,
    minimum: int = 3,
) -> np.ndarray:
    """Return one finite float64 series selected by ``value_label``."""
    frame = table_frame(form, sample_dim, feature_dim, step)
    values = np.asarray(numeric_column(frame, value_label, step), dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size < minimum:
        raise StepError(f"{step}: need at least {minimum} finite values")
    return values


def moving_range_sigma(values: np.ndarray, step: str) -> float:
    """Estimate short-term sigma from the average moving range.

    qcc uses the unbiasing constant 1.128 for individual measurements.  A
    constant series has no usable short-term scale and is rejected instead of
    silently producing zero-width limits.
    """
    moving_range = float(np.mean(np.abs(np.diff(values))))
    if not np.isfinite(moving_range) or moving_range <= 0:
        raise StepError(f"{step}: series must have non-zero variation")
    return moving_range / 1.128
