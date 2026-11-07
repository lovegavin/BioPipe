"""Shared helpers for propensity-score and matched-comparison operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError


def column(form, field_dim: str, name: str, operator: str):
    """Return a numeric column by field label, or raise a clear error."""
    labels = form.labels.get(field_dim, {}) or {}
    if name not in labels:
        raise StepError(f"{operator}: field '{name}' is required")
    index = int(labels[name])
    if index >= form.data.shape[1]:
        raise StepError(f"{operator}: field '{name}' is out of range")
    return np.asarray(form.data[:, index], dtype=float)


def treatment_vector(form, field_dim: str, name: str, operator: str) -> np.ndarray:
    values = column(form, field_dim, name, operator)
    if not np.all(np.isfinite(values)):
        raise StepError(f"{operator}: treatment '{name}' has non-finite values")
    rounded = np.rint(values)
    if not np.allclose(values, rounded):
        raise StepError(f"{operator}: treatment '{name}' must be 0/1")
    labels = rounded.astype(np.int64)
    if np.unique(labels).size != 2 or set(np.unique(labels).tolist()) != {0, 1}:
        raise StepError(f"{operator}: treatment '{name}' must contain both 0/1 values")
    return labels


def covariate_matrix(form, field_dim: str, names, operator: str) -> np.ndarray:
    names = [item.strip() for item in names if str(item).strip()]
    if not names:
        raise StepError(f"{operator}: at least one covariate is required")
    columns = [column(form, field_dim, name, operator) for name in names]
    matrix = np.column_stack(columns)
    if not np.all(np.isfinite(matrix)):
        raise StepError(f"{operator}: covariates must be finite")
    return matrix


def fit_logit(X: np.ndarray, y: np.ndarray, max_iter: int = 100, tol: float = 1e-10):
    """Fit an unpenalized logistic model by IRLS (matches R glm to 1e-10)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    design = np.column_stack([np.ones(X.shape[0], dtype=float), X])
    beta = np.zeros(design.shape[1], dtype=float)
    converged = False
    for iteration in range(1, max_iter + 1):
        eta = np.clip(design @ beta, -35.0, 35.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        weight = np.maximum(mu * (1.0 - mu), 1e-12)
        work = eta + (y - mu) / weight
        root = np.sqrt(weight)[:, None]
        updated, *_ = np.linalg.lstsq(root * design, root[:, 0] * work, rcond=None)
        if np.max(np.abs(updated - beta)) < tol:
            beta = updated
            converged = True
            break
        beta = updated
    if not converged:
        if not np.all(np.isfinite(beta)) or np.max(np.abs(beta)) > 60.0:
            raise StepError("propensity model did not converge")
    return beta, iteration


def sigmoid(values):
    clipped = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def roc_auc_score(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(np.int64)
    score = np.asarray(score, dtype=float)
    positives = int(np.sum(y == 1))
    negatives = int(np.sum(y == 0))
    if positives == 0 or negatives == 0:
        raise StepError("roc_auc requires both treated and control units")
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(score.size, dtype=float)
    sorted_score = score[order]
    start = 0
    while start < sorted_score.size:
        end = start + 1
        while end < sorted_score.size and sorted_score[end] == sorted_score[start]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    rank_sum = float(np.sum(ranks[y == 1]))
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def standardized_mean_difference(treated: np.ndarray, control: np.ndarray) -> float:
    if treated.size < 2 or control.size < 2:
        return float("nan")
    pooled = np.sqrt((np.var(treated, ddof=1) + np.var(control, ddof=1)) / 2.0)
    if pooled == 0:
        return float("nan")
    return float((treated.mean() - control.mean()) / pooled)


def variance_ratio(treated: np.ndarray, control: np.ndarray) -> float:
    if treated.size < 2 or control.size < 2:
        return float("nan")
    bottom = np.var(control, ddof=1)
    if bottom == 0:
        return float("nan")
    return float(np.var(treated, ddof=1) / bottom)


def matched_samples(form, sample_dim: str, field_dim: str, operator: str):
    """Return a boolean mask of units flagged as matched."""
    values = column(form, field_dim, "matched", operator)
    if not np.all(np.isin(np.rint(values), (0, 1))):
        raise StepError(f"{operator}: matched column must be 0/1")
    return np.rint(values).astype(bool)
