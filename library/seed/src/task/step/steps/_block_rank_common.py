"""Shared helpers for block-rank tests."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError


def block_matrix(form: Form, block_dim: str, treatment_dim: str, label: str):
    """Return a float matrix ordered as [block, treatment] plus ordered labels."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2D form, got ndim={form.data.ndim}")
    for dim in (block_dim, treatment_dim):
        if dim not in form.dims:
            raise StepError(f"{label}: dim {dim!r} not in {form.dims}")
    axis = form.dims.index(block_dim)
    y = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
    if y.ndim != 2 or y.shape[0] < 2 or y.shape[1] < 2:
        raise StepError(f"{label}: need at least two blocks and two treatments")
    blocks = [
        name for name, _ in sorted(form.labels[block_dim].items(), key=lambda item: item[1])
    ]
    treatments = [
        name
        for name, _ in sorted(form.labels[treatment_dim].items(), key=lambda item: item[1])
    ]
    if len(blocks) != y.shape[0] or len(treatments) != y.shape[1]:
        raise StepError(f"{label}: labels do not match the data shape")
    return y, blocks, treatments


def rank_blocks(y: np.ndarray) -> np.ndarray:
    """Rank each block's observed entries; missing entries stay NaN."""
    ranks = np.full_like(y, np.nan, dtype=np.float64)
    for row in range(y.shape[0]):
        observed = np.isfinite(y[row])
        if observed.any():
            ranks[row, observed] = stats.rankdata(y[row, observed], method="average")
    return ranks
