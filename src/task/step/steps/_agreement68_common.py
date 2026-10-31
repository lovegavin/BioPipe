"""Shared helpers for 0.68 inter-rater agreement coefficients."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def rating_matrix(form: Form, subject_dim: str, rater_dim: str, label: str):
    """Return ratings as subjects x raters plus category counts."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: input must be 2D")
    if subject_dim not in form.dims or rater_dim not in form.dims:
        raise StepError(f"{label}: expected dims {subject_dim!r}, {rater_dim!r}, got {form.dims}")
    if len(form.dims) != 2:
        raise StepError(f"{label}: input must have exactly two dimensions")
    matrix = np.asarray(form.data, dtype=np.float64)
    if form.dims.index(subject_dim) != 0:
        matrix = matrix.T
    if matrix.shape[0] < 2 or matrix.shape[1] < 2:
        raise StepError(f"{label}: need at least two subjects and two raters")
    finite = np.isfinite(matrix)
    values = np.unique(matrix[finite])
    if values.size < 2:
        raise StepError(f"{label}: need at least two distinct rating values")
    counts = np.stack([(matrix == value).sum(axis=1) for value in values], axis=1).astype(np.float64)
    rated = counts.sum(axis=1)
    if np.any(rated < 2):
        raise StepError(f"{label}: each subject needs at least two ratings")
    return matrix, values, counts, rated


def observed_agreement(counts: np.ndarray, rated: np.ndarray) -> float:
    pairs = np.sum(counts * (counts - 1.0), axis=1)
    return float(np.mean(pairs / (rated * (rated - 1.0))))


def gwet_pe(counts: np.ndarray, rated: np.ndarray) -> float:
    proportions = counts / rated[:, None]
    mean_p = proportions.mean(axis=0)
    return float(np.sum(mean_p * (1.0 - mean_p)) / (counts.shape[1] - 1.0))


def conger_pe(matrix: np.ndarray, values: np.ndarray) -> float:
    classified = np.stack([(matrix == value).sum(axis=0) for value in values], axis=1).astype(np.float64)
    rated = classified.sum(axis=1)
    if np.any(rated < 2):
        raise StepError("conger_kappa: each rater needs at least two ratings")
    proportions = classified / rated[:, None]
    n_raters = proportions.shape[0]
    mean_p = proportions.mean(axis=0)
    covariance = (proportions.T @ proportions - n_raters * np.outer(mean_p, mean_p)) / (n_raters - 1.0)
    return float(np.sum(mean_p * mean_p) - np.trace(covariance) / n_raters)


def coefficient(pa: float, pe: float, label: str) -> float:
    if not 0.0 <= pa <= 1.0:
        raise StepError(f"{label}: observed agreement is outside [0, 1]")
    if not 0.0 <= pe < 1.0:
        raise StepError(f"{label}: chance agreement must be in [0, 1)")
    return (pa - pe) / (1.0 - pe)
