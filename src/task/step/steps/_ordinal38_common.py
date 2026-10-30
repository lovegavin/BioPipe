"""Shared ordinal-association helpers for the 0.38 batch."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.step.steps._ext_common import labels_in_order, reorder, require_dims


def contingency(
    form: Form, row_dim: str, column_dim: str, label: str
) -> tuple[np.ndarray, list[str], list[str]]:
    require_dims(form, row_dim, column_dim, label=label)
    counts = np.asarray(reorder(form, row_dim, column_dim), dtype=np.float64)
    if counts.ndim != 2 or min(counts.shape) < 2:
        raise StepError(f"{label}: table must have at least two rows and two columns")
    if not np.isfinite(counts).all() or np.any(counts < 0):
        raise StepError(f"{label}: counts must be finite and non-negative")
    if counts.sum() <= 0:
        raise StepError(f"{label}: table total must be positive")
    if np.any(counts.sum(axis=0) <= 0) or np.any(counts.sum(axis=1) <= 0):
        raise StepError(f"{label}: table has an empty row or column")
    return counts, labels_in_order(form, row_dim), labels_in_order(form, column_dim)


def concordant_discordant(counts: np.ndarray) -> tuple[float, float]:
    rows, columns = counts.shape
    concordant = 0.0
    discordant = 0.0
    for i in range(rows):
        for j in range(i + 1, rows):
            for k in range(columns):
                for ell in range(k + 1, columns):
                    concordant += counts[i, k] * counts[j, ell]
                    discordant += counts[i, ell] * counts[j, k]
    return float(concordant), float(discordant)


def somers_d(counts: np.ndarray, direction: str) -> tuple[float, float, float, float]:
    concordant, discordant = concordant_discordant(counts)
    total = float(counts.sum())
    row_sums = counts.sum(axis=1)
    column_sums = counts.sum(axis=0)
    if direction == "row":
        margins = column_sums
    elif direction == "column":
        margins = row_sums
    else:
        raise StepError("somers_d: direction must be 'row' or 'column'")
    denominator = total * (total - 1.0) / 2.0 - float(np.sum(margins * (margins - 1.0) / 2.0))
    if denominator <= 0:
        raise StepError("somers_d: no comparable pairs after ties")
    return (concordant - discordant) / denominator, concordant, discordant, denominator


def goodman_kruskal_gamma(counts: np.ndarray) -> tuple[float, float, float]:
    concordant, discordant = concordant_discordant(counts)
    denominator = concordant + discordant
    if denominator <= 0:
        raise StepError("goodman_kruskal_gamma: no concordant or discordant pairs")
    return (concordant - discordant) / denominator, concordant, discordant


def kendall_w(
    form: Form,
    subject_dim: str,
    rater_dim: str,
    raters: list[str] | None,
    label: str,
) -> tuple[float, float, int, float, float, list[str], int, int]:
    require_dims(form, subject_dim, rater_dim, label=label)
    data = np.asarray(reorder(form, subject_dim, rater_dim), dtype=np.float64)
    if data.ndim != 2 or min(data.shape) < 2:
        raise StepError(f"{label}: need at least two subjects and two raters")
    if not np.isfinite(data).all():
        raise StepError(f"{label}: ratings must be finite")
    all_raters = labels_in_order(form, rater_dim)
    if raters:
        unknown = [name for name in raters if name not in all_raters]
        if unknown:
            raise StepError(f"{label}: unknown raters: {', '.join(unknown)}")
        indices = [all_raters.index(name) for name in raters]
        data = data[:, indices]
        selected = list(raters)
    else:
        selected = all_raters
    subjects, n_raters = data.shape
    ranked = np.empty_like(data)
    for j in range(n_raters):
        ranked[:, j] = stats.rankdata(data[:, j], method="average")
    rank_sums = ranked.sum(axis=1)
    center = n_raters * (subjects + 1) / 2.0
    s_value = float(np.sum((rank_sums - center) ** 2))
    denominator = n_raters**2 * (subjects**3 - subjects)
    if denominator <= 0:
        raise StepError(f"{label}: invalid subject/rater dimensions")
    w_value = 12.0 * s_value / denominator
    chisq = n_raters * (subjects - 1) * w_value
    df = subjects - 1
    p_value = float(stats.chi2.sf(chisq, df))
    return w_value, chisq, df, p_value, s_value, selected, subjects, n_raters
