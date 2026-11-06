"""Helpers for cross-validated model assessment (sklearn-compatible)."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.steps._ml_utils import (
    accuracy, fit_logistic, label_vector, matrix, predict_proba, roc_auc,
    stratified_folds,
)


def standardize(train: np.ndarray, other: np.ndarray):
    mean = train.mean(axis=0)
    std = train.std(axis=0)
    std = np.where(std == 0.0, 1.0, std)
    return (train - mean) / std, (other - mean) / std


def score(y: np.ndarray, proba: np.ndarray, metric: str) -> float:
    if metric == 'accuracy':
        return accuracy(y, proba)
    if metric == 'roc_auc':
        return roc_auc(y, proba)
    raise StepError(f"unknown scoring metric {metric!r}")


def fit_score(Xtr, ytr, Xte, yte, C, standardize_features, metric):
    if standardize_features:
        Xtr, Xte = standardize(Xtr, Xte)
    coef, intercept, _ = fit_logistic(Xtr, ytr, C=C)
    return score(yte, predict_proba(Xte, coef, intercept), metric)


def learning_curve(X, y, fractions, n_splits, seed, C, standardize_features, metric):
    folds = stratified_folds(y, n_splits, True, seed)
    n = y.size
    n_max_train = n - int(np.ceil(n / n_splits))
    sizes = sorted({max(1, int(np.ceil(f * n_max_train))) for f in fractions})
    rows = []
    for size in sizes:
        train_scores, test_scores = [], []
        for k in range(n_splits):
            train_idx = np.where(folds != k)[0][:size]
            test_idx = np.where(folds == k)[0]
            if train_idx.size < 2 or np.unique(y[train_idx]).size < 2:
                continue
            Xtr, Xte = X[train_idx], X[test_idx]
            if standardize_features:
                Xtr, Xte = standardize(Xtr, Xte)
            coef, intercept, _ = fit_logistic(Xtr, y[train_idx], C=C)
            train_scores.append(score(y[train_idx], predict_proba(Xtr, coef, intercept), metric))
            test_scores.append(score(y[test_idx], predict_proba(Xte, coef, intercept), metric))
        rows.append((size, float(np.mean(train_scores)), float(np.std(train_scores)),
                     float(np.mean(test_scores)), float(np.std(test_scores))))
    return rows


def grid_search(X, y, values, n_splits, seed, standardize_features, metric):
    folds = stratified_folds(y, n_splits, True, seed)
    rows = []
    for value in values:
        scores = []
        for k in range(n_splits):
            train_idx = np.where(folds != k)[0]
            test_idx = np.where(folds == k)[0]
            Xtr, Xte = X[train_idx], X[test_idx]
            if standardize_features:
                Xtr, Xte = standardize(Xtr, Xte)
            coef, intercept, _ = fit_logistic(Xtr, y[train_idx], C=value)
            scores.append(score(y[test_idx], predict_proba(Xte, coef, intercept), metric))
        rows.append((float(value), float(np.mean(scores)), float(np.std(scores))))
    best = max(rows, key=lambda r: r[1])
    return rows, best[0]


def bh_adjust(p: np.ndarray, method: str) -> np.ndarray:
    n = p.size
    order = np.argsort(p, kind='mergesort')
    ranked = p[order]
    if method == 'bonferroni':
        adjusted = np.minimum(1.0, ranked * n)
    elif method == 'holm':
        adjusted = np.minimum(1.0, np.maximum.accumulate((n - np.arange(n)) * ranked))
    elif method in ('bh', 'by'):
        factor = n / (np.arange(n) + 1.0)
        raw = np.minimum(1.0, ranked * factor)
        adjusted = np.minimum.accumulate(raw[::-1])[::-1]
        if method == 'by':
            adjusted = np.minimum(1.0, adjusted * np.sum(1.0 / np.arange(1, n + 1)))
    else:
        raise StepError(f"unknown multiple-testing method {method!r}")
    out = np.empty(n)
    out[order] = np.minimum(1.0, adjusted)
    return out
