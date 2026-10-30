"""Shared helpers for the 0.39 multivariate and robust tests."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core import StepError

from ._ext_common import group_values, labels_in_order, reorder, require_dims


def group_key(value) -> str:
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number)
    except (TypeError, ValueError):
        return str(value)


def select_groups(expr, meta, sample_dim, feature_dim, group_dim, group_label, group_a, group_b, label):
    require_dims(expr, feature_dim, sample_dim, label=label)
    require_dims(meta, group_dim, label=f"{label} metadata")
    a = group_key(group_a)
    b = group_key(group_b)
    if a == b:
        raise StepError(f"{label}: group_a and group_b must differ")
    samples = labels_in_order(expr, sample_dim)
    meta_samples, values = group_values(meta, sample_dim, group_label)
    by_sample = {sample: group_key(value) for sample, value in zip(meta_samples, values)}
    keep = [i for i, sample in enumerate(samples) if by_sample.get(sample) in (a, b)]
    if not keep:
        raise StepError(f"{label}: no samples in the requested groups")
    codes = np.asarray([0 if by_sample[samples[i]] == a else 1 for i in keep], dtype=np.int64)
    if int((codes == 0).sum()) < 2 or int((codes == 1).sum()) < 2:
        raise StepError(f"{label}: need at least two samples in each group")
    data = reorder(expr, sample_dim, feature_dim)[keep]
    return data, codes, [samples[i] for i in keep], a, b


def yuen_columns(a, b, trim: float, confidence: float):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return None
    if not (0 <= trim < 0.5):
        raise StepError("yuen_test: trim must be in [0, 0.5)")
    ga = int(math.floor(trim * a.size))
    gb = int(math.floor(trim * b.size))
    if a.size - 2 * ga < 2 or b.size - 2 * gb < 2:
        return None
    sa = np.sort(a)
    sb = np.sort(b)
    ma = float(np.mean(sa[ga:a.size - ga]))
    mb = float(np.mean(sb[gb:b.size - gb]))
    qa = np.quantile(a, [trim, 1.0 - trim])
    qb = np.quantile(b, [trim, 1.0 - trim])
    wa = np.clip(a, qa[0], qa[1])
    wb = np.clip(b, qb[0], qb[1])
    va = float(np.var(wa, ddof=1))
    vb = float(np.var(wb, ddof=1))
    dfa = a.size - 2 * ga - 1
    dfb = b.size - 2 * gb - 1
    if dfa <= 0 or dfb <= 0:
        return None
    va_n = (a.size - 1) * va / ((dfa + 1) * dfa)
    vb_n = (b.size - 1) * vb / ((dfb + 1) * dfb)
    se = math.sqrt(va_n + vb_n)
    if se <= 0:
        return None
    df = (va_n + vb_n) ** 2 / (va_n ** 2 / dfa + vb_n ** 2 / dfb)
    diff = ma - mb
    t_value = diff / se
    p_value = float(2.0 * stats.t.sf(abs(t_value), df))
    crit = float(stats.t.ppf(0.5 + confidence / 2.0, df))
    return [diff, t_value, df, p_value, diff - crit * se, diff + crit * se, ma, mb, float(a.size), float(b.size)]
