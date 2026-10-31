"""Shared helpers for 0.69 entropy and long-memory operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def numeric_series(form, sample_dim: str, feature_dim: str, value_label: str, step: str) -> np.ndarray:
    """Return finite float64 values from a one-column table."""
    frame = table_frame(form, sample_dim, feature_dim, step)
    values = np.asarray(numeric_column(frame, value_label, step), dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size < 5:
        raise StepError(f"{step}: at least 5 finite values are required")
    return values


def default_radius(values: np.ndarray) -> float:
    """R pracma's default tolerance: 0.2 * sample standard deviation."""
    sd = float(np.std(values, ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        raise StepError("approximate entropy requires non-zero variance")
    return 0.2 * sd
