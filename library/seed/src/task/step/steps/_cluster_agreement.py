"""Helpers for comparing two label columns on shared samples."""
from __future__ import annotations

from src.core import StepError
from ._metric_common import label_series


def paired_labels(
    first,
    second,
    sample_dim: str,
    label_dim: str,
    first_label: str,
    second_label: str,
    step: str,
):
    """Return aligned class labels from two forms, preserving first-form order."""
    first_samples, first_values = label_series(first, sample_dim, label_dim, first_label, step)
    second_samples, second_values = label_series(second, sample_dim, label_dim, second_label, step)
    second_pos = {name: i for i, name in enumerate(second_samples)}
    left, right = [], []
    for i, name in enumerate(first_samples):
        if name not in second_pos:
            continue
        if first_values[i] is None or second_values[second_pos[name]] is None:
            raise StepError(f"{step}: class labels must not be missing")
        left.append(first_values[i])
        right.append(second_values[second_pos[name]])
    if len(left) < 2:
        raise StepError(f"{step}: need at least two shared samples")
    return left, right
