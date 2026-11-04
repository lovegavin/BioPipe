"""Helpers for 0.63 cross-correlation, sign, and BDS tests."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from ._metric_common import score_series


def numeric_series(form, sample_dim: str, value_dim: str, value_label: str, step: str):
    samples, values = score_series(form, sample_dim, value_dim, value_label)
    keep = np.isfinite(values)
    if int(keep.sum()) < 3:
        raise StepError(f"{step}: need at least three finite observations")
    return [samples[i] for i in np.flatnonzero(keep)], np.asarray(values[keep], dtype=np.float64)


def aligned_series(
    first,
    second,
    sample_dim: str,
    value_dim: str,
    first_label: str,
    second_label: str,
    step: str,
):
    left_samples, left = numeric_series(first, sample_dim, value_dim, first_label, step)
    right_samples, right = numeric_series(second, sample_dim, value_dim, second_label, step)
    right_pos = {name: i for i, name in enumerate(right_samples)}
    xs, ys = [], []
    for i, name in enumerate(left_samples):
        if name not in right_pos:
            continue
        value = right[right_pos[name]]
        if not np.isfinite(value):
            continue
        xs.append(left[i])
        ys.append(value)
    if len(xs) < 3:
        raise StepError(f"{step}: need at least three shared finite samples")
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
