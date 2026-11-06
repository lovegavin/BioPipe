"""Shared helpers for single-cell differential expression operators."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def matrix2d(form: Form, rows_dim: str, cols_dim: str, operator: str) -> np.ndarray:
    if not isinstance(form, Form) or form.data.ndim != 2:
        raise StepError(f"{operator}: expected a 2D matrix")
    if list(form.dims) != [rows_dim, cols_dim]:
        raise StepError(
            f"{operator}: expected dims [{rows_dim}, {cols_dim}], got {list(form.dims)}"
        )
    data = np.asarray(form.data, dtype=float)
    if not np.all(np.isfinite(data)):
        raise StepError(f"{operator}: matrix contains NaN or infinite values")
    return data


def axis_labels(form: Form, dim: str, n: int, operator: str) -> list[str]:
    labels = (form.labels or {}).get(dim) or {}
    names = [str(name) for name, _ in sorted(labels.items(), key=lambda item: item[1])]
    if len(names) != n:
        names = [str(index) for index in range(n)]
    return names


def group_ids(form: Form, n_cells: int, cell_dim: str, group_dim: str, operator: str) -> list[str]:
    if not isinstance(form, Form) or form.data.ndim != 2:
        raise StepError(f"{operator}: groups must be a 2D matrix")
    labels = (form.labels or {}).get(group_dim) or {}
    if labels:
        names = [None] * len(labels)
        for name, position in labels.items():
            names[int(position)] = str(name)
        if None not in names and len(names) == n_cells:
            return names
    if form.data.shape[0] != n_cells:
        raise StepError(f"{operator}: one group label per cell is required")
    column = form.data[:, 0]
    encoders = (form.info or {}).get("encoders") or {}
    encoder = encoders.get(group_dim) if isinstance(encoders, dict) else None
    inverse = getattr(encoder, "inverse", None)
    if isinstance(inverse, dict) and inverse:
        return [str(inverse[int(round(float(value)))]) for value in column]
    return [f"{float(value):g}" for value in column]


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_values = values[order]
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and sorted_values[end] == sorted_values[start]:
            end += 1
        ranks[order[start:end]] = (start + end + 1) / 2.0
        start = end
    return ranks


def wilcoxon_rank_sum(inside: np.ndarray, outside: np.ndarray) -> tuple[float, float, float]:
    n1 = len(inside)
    n2 = len(outside)
    if n1 == 0 or n2 == 0:
        return 0.0, 0.0, 1.0
    combined = np.concatenate([inside, outside])
    ranks = rankdata(combined)
    rank_sum = float(ranks[:n1].sum())
    u_value = rank_sum - n1 * (n1 + 1) / 2.0
    mean_u = n1 * n2 / 2.0
    _, counts = np.unique(combined, return_counts=True)
    tie = float(np.sum(counts.astype(float) ** 3 - counts.astype(float)))
    n = n1 + n2
    variance = n1 * n2 / 12.0 * ((n + 1) - tie / (n * (n - 1)))
    if variance <= 0.0:
        return u_value, 0.0, 1.0
    z_value = (u_value - mean_u) / np.sqrt(variance)
    return u_value, float(z_value), normal_two_sided_p(float(z_value))


def normal_two_sided_p(z_value: float) -> float:
    import math

    return float(math.erfc(abs(z_value) / math.sqrt(2.0)))


def bh_adjust(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    scaled = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)
    out = np.empty(n, dtype=float)
    out[order] = adjusted
    return out


def log2_fold_change(inside: np.ndarray, outside: np.ndarray) -> float:
    a = float(np.mean(inside)) + 1e-9
    b = float(np.mean(outside)) + 1e-9
    return float(np.log2(a / b))
