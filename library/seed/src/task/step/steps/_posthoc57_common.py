"""Shared helpers for the 0.57 all-pairs mean comparisons."""
from __future__ import annotations

import numpy as np


def finite_group_values(columns, feature_index: int, groups, label: str):
    """Return one finite vector per group, or None when a group is too small."""
    values = []
    for column in columns:
        vector = np.asarray(column[:, feature_index], dtype=np.float64)
        vector = vector[np.isfinite(vector)]
        if vector.size < 2:
            return None
        values.append(vector)
    if len(values) < 2:
        return None
    return values


def pairs(group_count: int):
    """Yield lower-triangle group index pairs in R pairwise-table order."""
    for second in range(1, group_count):
        for first in range(second):
            yield first, second
