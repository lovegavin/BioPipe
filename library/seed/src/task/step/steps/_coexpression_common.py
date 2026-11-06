"""Shared helpers for co-expression network operators.

The scale-free fit follows WGCNA's ``scaleFreeFitIndex`` (equal-width
discretisation of the connectivity, log-log linear fit, plus the truncated
exponential adjusted R^2).  TOM follows the standard WGCNA formula.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError


def ordered(labels: dict) -> list[str]:
    return [name for name, _ in sorted(labels.items(), key=lambda item: item[1])]


def expression_matrix(form, sample_dim: str, feature_dim: str):
    if form.data.ndim != 2:
        raise StepError(f"expected a 2D form, got ndim={form.data.ndim}")
    if sample_dim not in form.dims or feature_dim not in form.dims:
        raise StepError(
            f"expected dims {sample_dim!r} and {feature_dim!r}, got {form.dims}"
        )
    axis = form.dims.index(sample_dim)
    X = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
    if X.shape[0] < 3 or X.shape[1] < 2:
        raise StepError("need at least three samples and two features")
    col_mean = np.nanmean(X, axis=0)
    col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
    X = np.where(np.isfinite(X), X, col_mean)
    samples = ordered(form.labels[sample_dim])
    features = ordered(form.labels[feature_dim])
    if len(samples) != X.shape[0] or len(features) != X.shape[1]:
        raise StepError("axis labels do not match the data shape")
    return X, samples, features


def select_features(X: np.ndarray, max_features: int) -> np.ndarray:
    """Indices of the most variable features (all features when max<=0)."""
    n = X.shape[1]
    if max_features is None or int(max_features) <= 0 or int(max_features) >= n:
        return np.arange(n)
    var = X.var(axis=0, ddof=1)
    order = np.argsort(-var, kind="mergesort")
    return np.sort(order[: int(max_features)])


def correlation(X: np.ndarray) -> np.ndarray:
    """Pearson correlation between columns, NaN treated as zero variance."""
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.corrcoef(X, rowvar=False)
    if R.ndim == 0:
        R = np.array([[1.0]])
    R = np.atleast_2d(R)
    bad = ~np.isfinite(R)
    R[bad] = 0.0
    np.fill_diagonal(R, 1.0)
    return R


def scale_free_fit(k: np.ndarray, n_bins: int = 10, remove_first: bool = False):
    """Port of WGCNA ``scaleFreeFitIndex`` (same discretisation and fits)."""
    k = np.asarray(k, dtype=np.float64)
    k = k[np.isfinite(k)]
    empty = {"r_squared": np.nan, "slope": np.nan, "adj_r_squared": np.nan}
    if k.size < 3 or np.ptp(k) == 0:
        return empty
    n_bins = max(3, int(n_bins))
    lo, hi = float(k.min()), float(k.max())
    edges = np.linspace(lo, hi, n_bins + 1)
    mids = (edges[:-1] + edges[1:]) / 2.0

    # R cut(): intervals are right-closed (a, b]; the minimum falls outside.
    idx = np.searchsorted(edges, k, side="left") - 1
    idx = np.clip(idx, 0, n_bins - 1)
    valid = np.ones(idx.shape, dtype=bool)
    counts = np.bincount(idx[valid], minlength=n_bins) if valid.any() else np.zeros(n_bins)
    sums = (
        np.bincount(idx[valid], weights=k[valid], minlength=n_bins)
        if valid.any()
        else np.zeros(n_bins)
    )
    dk = np.where(counts > 0, sums / np.maximum(counts, 1), mids)
    dk = np.where(dk == 0, mids, dk)
    p_dk = counts.astype(np.float64) / float(k.size)

    log_dk = np.log10(dk)
    log_p = np.log10(p_dk + 1e-9)
    if remove_first:
        log_dk = log_dk[1:]
        log_p = log_p[1:]
    if log_dk.size < 3 or np.ptp(log_dk) == 0:
        return empty

    slope, intercept = np.polyfit(log_dk, log_p, 1)
    fitted = slope * log_dk + intercept
    ss_res = float(np.sum((log_p - fitted) ** 2))
    ss_tot = float(np.sum((log_p - log_p.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan

    design = np.column_stack([np.ones_like(log_dk), log_dk, 10.0 ** log_dk])
    coef, *_ = np.linalg.lstsq(design, log_p, rcond=None)
    resid = log_p - design @ coef
    ss_res2 = float(np.sum(resid ** 2))
    r2_2 = 1.0 - ss_res2 / ss_tot if ss_tot > 0 else np.nan
    n = log_dk.size
    adj = 1.0 - (1.0 - r2_2) * (n - 1) / (n - 3) if n > 3 and np.isfinite(r2_2) else np.nan
    return {"r_squared": r_squared, "slope": float(slope), "adj_r_squared": adj}


def adjacency(R: np.ndarray, beta: float) -> np.ndarray:
    A = np.abs(R) ** float(beta)
    np.fill_diagonal(A, 0.0)
    return A


def tom(A: np.ndarray) -> np.ndarray:
    """Topological overlap matrix for a symmetric adjacency."""
    k = A.sum(axis=1)
    shared = A @ A
    denom = np.minimum(k[:, None], k[None, :]) + 1.0 - A
    denom = np.where(denom <= 0, 1.0, denom)
    T = (shared + A) / denom
    T = np.clip(T, 0.0, 1.0)
    np.fill_diagonal(T, 0.0)
    return T


def module_eigengenes(X: np.ndarray, labels: np.ndarray, scale: bool = True):
    """PC1 of each module, sign-aligned to the module average expression."""
    ids = sorted(int(v) for v in np.unique(labels) if int(v) > 0)
    if not ids:
        raise StepError("no modules to summarise")
    out = np.zeros((X.shape[0], len(ids)), dtype=np.float64)
    var_explained = []
    for j, mid in enumerate(ids):
        block = X[:, labels == mid]
        if block.shape[1] == 0:
            continue
        if scale:
            sd = block.std(axis=0, ddof=1)
            sd = np.where(sd > 0, sd, 1.0)
            block = (block - block.mean(axis=0)) / sd
        U, S, _ = np.linalg.svd(block, full_matrices=False)
        pc = U[:, 0] * S[0]
        avg = block.mean(axis=1)
        if np.corrcoef(pc, avg)[0, 1] < 0:
            pc = -pc
        out[:, j] = pc
        total = float(np.sum(S ** 2))
        var_explained.append(float(S[0] ** 2 / total) if total > 0 else np.nan)
    return ids, out, var_explained


def cor_pvalue(r: np.ndarray, n: int) -> np.ndarray:
    from scipy import stats

    r = np.clip(np.asarray(r, dtype=np.float64), -0.999999999, 0.999999999)
    if n <= 2:
        return np.full(r.shape, np.nan)
    t = r * np.sqrt((n - 2) / (1.0 - r * r))
    return 2.0 * stats.t.sf(np.abs(t), df=n - 2)
