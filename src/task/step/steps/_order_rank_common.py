"""Shared alignment and isotonic helpers for ordered rank tests."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from ._tests50_common import grouped_expression


def align_ordered(
    expression,
    meta,
    sample_dim: str,
    feature_dim: str,
    group_dim: str,
    group_label: str,
    group_order,
    label: str,
):
    """Align a feature table and return a validated group order."""
    values, features, _samples, groups, observed = grouped_expression(
        expression,
        meta,
        sample_dim,
        feature_dim,
        group_dim,
        group_label,
    )
    if group_order:
        order = [str(value) for value in group_order]
        if len(set(order)) != len(order):
            raise StepError(f"{label}: group_order contains duplicates")
        missing = [group for group in observed if group not in order]
        unknown = [group for group in order if group not in set(observed)]
        if missing or unknown:
            raise StepError(
                f"{label}: group_order must cover observed groups; "
                f"missing={missing}, unknown={unknown}"
            )
    else:
        order = list(observed)
    if len(order) < 2:
        raise StepError(f"{label}: at least two groups are required")
    indices = {
        group: np.asarray(
            [index for index, value in enumerate(groups) if value == group],
            dtype=np.int64,
        )
        for group in order
    }
    return values, features, order, indices


def finite_groups(row: np.ndarray, indices, order, label: str):
    """Return finite group vectors, or None when a group is too small."""
    groups = []
    for group in order:
        values = np.asarray(row[indices[group]], dtype=np.float64)
        values = values[np.isfinite(values)]
        if values.size < 2:
            return None
        groups.append(values)
    if sum(group.size for group in groups) < 2 * len(order):
        return None
    return groups


def pava(values, weights, increasing: bool = True) -> np.ndarray:
    """Weighted pool-adjacent-violators regression."""
    y = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if y.size != w.size or y.size == 0:
        raise StepError("pava: values and weights must have the same nonzero length")
    if not np.isfinite(y).all() or not np.isfinite(w).all() or np.any(w <= 0):
        raise StepError("pava: values must be finite and weights positive")
    if not increasing:
        return pava(y[::-1], w[::-1], True)[::-1]

    blocks: list[list[float]] = []
    for value, weight in zip(y, w):
        total = float(value * weight)
        mass = float(weight)
        count = 1
        while blocks and blocks[-1][0] > total / mass:
            previous_mean, previous_mass, previous_count = blocks.pop()
            total += previous_mean * previous_mass
            mass += previous_mass
            count += previous_count
        blocks.append([total / mass, mass, count])

    result = []
    for mean, _mass, count in blocks:
        result.extend([mean] * count)
    return np.asarray(result, dtype=np.float64)
