"""Shared helpers for model-selection operators (numpy/scipy only)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from src.core import StepError


def label_vector(form, dim: str, operator: str) -> np.ndarray:
    """Return a 1-D integer label vector from a Form with a single column."""
    data = np.asarray(form.data)
    if data.ndim == 1:
        values = data
    elif data.ndim == 2 and data.shape[1] == 1:
        values = data[:, 0]
    else:
        raise StepError(f"{operator}: labels must be a single column")
    if values.size < 4:
        raise StepError(f"{operator}: need at least 4 labeled samples")
    rounded = np.rint(values.astype(float))
    if not np.allclose(values, rounded):
        raise StepError(f"{operator}: labels must be integers")
    labels = rounded.astype(np.int64)
    if np.unique(labels).size < 2:
        raise StepError(f"{operator}: need at least two classes")
    return labels


def matrix(form, operator: str) -> np.ndarray:
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2:
        raise StepError(f"{operator}: feature matrix must be 2-D")
    if not np.all(np.isfinite(data)):
        raise StepError(f"{operator}: feature matrix has non-finite values")
    if data.shape[1] < 1:
        raise StepError(f"{operator}: feature matrix has no columns")
    return data


def stratified_folds(labels: np.ndarray, n_splits: int, shuffle: bool, seed: int) -> np.ndarray:
    """Reproduce sklearn StratifiedKFold test-fold assignment."""
    if n_splits < 2:
        raise StepError("n_splits must be at least 2")
    y = np.asarray(labels)
    _, y_idx, y_inv = np.unique(y, return_index=True, return_inverse=True)
    _, class_perm = np.unique(y_idx, return_inverse=True)
    y_encoded = class_perm[y_inv]
    y_counts = np.bincount(y_encoded)
    if np.all(n_splits > y_counts):
        raise StepError("n_splits cannot be greater than the members of each class")
    y_order = np.sort(y_encoded)
    allocation = np.asarray(
        [np.bincount(y_order[i::n_splits], minlength=len(y_idx)) for i in range(n_splits)]
    )
    rng = np.random.RandomState(seed)
    test_folds = np.empty(len(y), dtype=np.int64)
    for k in range(len(y_idx)):
        folds_for_class = np.arange(n_splits).repeat(allocation[:, k])
        if shuffle:
            rng.shuffle(folds_for_class)
        test_folds[y_encoded == k] = folds_for_class
    return test_folds


def _approximate_mode(class_counts: np.ndarray, n_draws: int, rng) -> np.ndarray:
    continuous = class_counts / class_counts.sum() * n_draws
    floored = np.floor(continuous)
    need_to_add = int(n_draws - floored.sum())
    if need_to_add > 0:
        remainder = continuous - floored
        values = np.sort(np.unique(remainder))[::-1]
        for value in values:
            inds = np.where(remainder == value)[0]
            add_now = min(len(inds), need_to_add)
            chosen = rng.choice(inds, size=add_now, replace=False)
            floored[chosen] += 1
            need_to_add -= add_now
            if need_to_add == 0:
                break
    return floored.astype(np.int64)


def stratified_split(labels: np.ndarray, test_fraction: float, seed: int) -> np.ndarray:
    """Return a boolean mask (True = test) matching StratifiedShuffleSplit."""
    if not 0.0 < test_fraction < 1.0:
        raise StepError("test_fraction must be between 0 and 1")
    y = np.asarray(labels)
    n_samples = y.size
    n_test = int(np.ceil(test_fraction * n_samples))
    n_train = n_samples - n_test
    classes, y_indices = np.unique(y, return_inverse=True)
    class_counts = np.bincount(y_indices)
    if np.min(class_counts) < 2:
        raise StepError("the least populated class has fewer than 2 members")
    if n_train < classes.size or n_test < classes.size:
        raise StepError("test_fraction leaves fewer samples than classes")
    class_indices = np.split(
        np.argsort(y_indices, kind="mergesort"), np.cumsum(class_counts)[:-1]
    )
    rng = np.random.RandomState(seed)
    n_i = _approximate_mode(class_counts, n_train, rng)
    remaining = class_counts - n_i
    t_i = _approximate_mode(remaining, n_test, rng)
    mask = np.zeros(n_samples, dtype=bool)
    for i in range(classes.size):
        permutation = rng.permutation(class_counts[i])
        indices = class_indices[i].take(permutation, mode="clip")
        test_part = indices[n_i[i] : n_i[i] + t_i[i]]
        mask[test_part] = True
    return mask


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def fit_logistic(
    X: np.ndarray,
    y: np.ndarray,
    C: float = 1.0,
    fit_intercept: bool = True,
    max_iter: int = 1000,
):
    """L2-regularized logistic regression (sklearn-compatible objective)."""
    if C <= 0:
        raise StepError("C must be positive")
    y = np.asarray(y, dtype=float)
    n, d = X.shape
    Xa = np.hstack([np.ones((n, 1)), X]) if fit_intercept else X
    p = Xa.shape[1]

    def objective(w):
        z = Xa @ w
        loss = np.logaddexp(0.0, z) - y * z
        f = 0.5 * np.dot(w[1 if fit_intercept else 0 :], w[1 if fit_intercept else 0 :])
        f += C * loss.sum()
        grad = C * (Xa.T @ (_sigmoid(z) - y))
        if fit_intercept:
            grad = grad.copy()
            grad[1:] += w[1:]
        else:
            grad = grad + w
        return f, grad

    result = minimize(
        objective,
        np.zeros(p),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": int(max_iter), "gtol": 1e-10, "ftol": 1e-14},
    )
    if not result.success and result.status not in (1, 2):
        raise StepError(f"logistic regression did not converge: {result.message}")
    w = result.x
    intercept = float(w[0]) if fit_intercept else 0.0
    coef = w[1:] if fit_intercept else w
    return coef, intercept, int(result.nit)


def predict_proba(X: np.ndarray, coef: np.ndarray, intercept: float) -> np.ndarray:
    return _sigmoid(X @ coef + intercept)


def accuracy(y: np.ndarray, proba: np.ndarray) -> float:
    pred = (proba >= 0.5).astype(np.int64)
    return float(np.mean(pred == np.asarray(y, dtype=np.int64)))


def roc_auc(y: np.ndarray, scores: np.ndarray) -> float:
    """Area under the ROC curve using the trapezoidal rule."""
    y = np.asarray(y, dtype=np.int64)
    order = np.argsort(-scores, kind="mergesort")
    y = y[order]
    scores = np.asarray(scores)[order]
    distinct = np.where(np.diff(scores))[0]
    threshold_idxs = np.r_[distinct, y.size - 1]
    tps = np.cumsum(y)[threshold_idxs]
    fps = 1 + threshold_idxs - tps
    if tps[-1] == 0 or fps[-1] == 0:
        raise StepError("ROC AUC is undefined with a single class")
    tpr = np.r_[0.0, tps / tps[-1]]
    fpr = np.r_[0.0, fps / fps[-1]]
    return float(np.sum((tpr[1:] + tpr[:-1]) * np.diff(fpr) / 2.0))


def log_loss(y: np.ndarray, proba: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    p = np.clip(proba, 1e-15, 1 - 1e-15)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
