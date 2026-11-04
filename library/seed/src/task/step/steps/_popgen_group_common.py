"""Shared population selection for the Fst-family operators."""
from __future__ import annotations

from src.core import StepError

from ._ext_common import group_values, labels_in_order


def group_indices(form, sample_dim: str, meta, group_label: str,
                  group_a, group_b, label: str) -> tuple[list[int], list[int]]:
    """Return genotype column indices for two labelled population groups."""
    samples = labels_in_order(form, sample_dim)
    meta_samples, groups = group_values(meta, sample_dim, group_label)
    mpos = {name: i for i, name in enumerate(meta_samples)}

    def same(value, target):
        try:
            return float(value) == float(target)
        except (TypeError, ValueError):
            return str(value) == str(target)

    for target in (group_a, group_b):
        if not any(same(value, target) for value in groups):
            raise StepError(
                f"{label}: group {target!r} not found in {group_label!r}"
            )
    ia = [i for i, name in enumerate(samples)
          if name in mpos and same(groups[mpos[name]], group_a)]
    ib = [i for i, name in enumerate(samples)
          if name in mpos and same(groups[mpos[name]], group_b)]
    if len(ia) < 2 or len(ib) < 2:
        raise StepError(
            f"{label} needs at least two genotyped samples in each group"
        )
    return ia, ib
