"""Shared compositional differential-abundance kernels."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError

from ._ext_common import group_values, labels_in_order, reorder, require_dims


def prepare(table, meta, sample_dim, taxon_dim, group_label, group_a, group_b):
    require_dims(table, sample_dim, taxon_dim, label="table")
    require_dims(meta, sample_dim, label="metadata")
    meta_samples, values = group_values(meta, sample_dim, group_label)
    values = np.asarray(values)
    data = reorder(table, sample_dim, taxon_dim)
    table_samples = labels_in_order(table, sample_dim)
    positions = {s: i for i, s in enumerate(table_samples)}
    if any(s not in positions for s in meta_samples):
        raise StepError("metadata contains samples absent from the abundance table")
    groups = {}
    for sample, group in zip(meta_samples, values):
        groups.setdefault(str(group), []).append(positions[sample])
    if str(group_a) not in groups or str(group_b) not in groups:
        raise StepError(f"groups {group_a!r}/{group_b!r} not present")
    taxa = labels_in_order(table, taxon_dim)
    return data, groups[str(group_a)], groups[str(group_b)], taxa


def clr_test(data, a, b, *, n_mc=128, seed=0, pseudocount=0.5, monte_carlo=True):
    """CLR-based Welch test used by the ALDEx-style operator."""
    rng = np.random.default_rng(seed)
    xa, xb = data[a], data[b]
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        raise StepError("each group needs at least two samples")
    if monte_carlo:
        def instance(block):
            gamma = rng.gamma(shape=block + pseudocount, scale=1.0)
            return np.log(gamma / gamma.sum(axis=1, keepdims=True))
        pvals = []
        effects = []
        for _ in range(n_mc):
            la, lb = instance(xa), instance(xb)
            diff = lb.mean(axis=0) - la.mean(axis=0)
            effects.append(diff)
            pvals.append(stats.ttest_ind(la, lb, axis=0, equal_var=False).pvalue)
        diff = np.mean(effects, axis=0)
        p = np.median(np.asarray(pvals), axis=0)
    else:
        la = np.log(xa + pseudocount)
        lb = np.log(xb + pseudocount)
        la = la - la.mean(axis=1, keepdims=True)
        lb = lb - lb.mean(axis=1, keepdims=True)
        diff = lb.mean(axis=0) - la.mean(axis=0)
        p = stats.ttest_ind(la, lb, axis=0, equal_var=False).pvalue
    effect = diff
    return diff, effect, np.clip(p, 0, 1), n1, n2


def ancom_style(data, a, b, *, pseudocount=1.0):
    """Log-ratio group contrast with sample bias removed."""
    xa, xb = data[a], data[b]
    la = np.log(xa + pseudocount)
    lb = np.log(xb + pseudocount)
    la = la - la.mean(axis=1, keepdims=True)
    lb = lb - lb.mean(axis=1, keepdims=True)
    diff = lb.mean(axis=0) - la.mean(axis=0)
    p = stats.ttest_ind(la, lb, axis=0, equal_var=False).pvalue
    return diff, np.abs(diff), np.clip(p, 0, 1), len(a), len(b)
