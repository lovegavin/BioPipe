"""Shared helpers for the community-ecology operators.

The 1.6.0 batch (SIMPER, MRPP, species accumulation) all start from a
sample x taxon abundance table plus a sample metadata table. This
module validates those two inputs and normalizes group labels so that
numeric encodings (``0`` / ``0.0``) and string labels compare the same
way.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist, squareform

from src.core import StepError
from src.task.step.steps._ext_common import group_values, labels_in_order, reorder

_MISSING = {"", "nan", "none", "null"}


def abundance(form, sample_dim: str, taxon_dim: str, label: str):
    """Validate a [sample, taxon] abundance table and return float64 data."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2-D abundance table, got {form.data.ndim} dims")
    if sample_dim not in form.dims or taxon_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {sample_dim!r} and {taxon_dim!r}, got {list(form.dims)}"
        )
    data = reorder(form, sample_dim, taxon_dim).astype(np.float64)
    missing = form.info.get("missing_code", np.nan)
    if isinstance(missing, float) and np.isnan(missing):
        data = np.where(np.isnan(data), 0.0, data)
    else:
        data = np.where(data == missing, 0.0, data)
    if not np.all(np.isfinite(data)):
        raise StepError(f"{label}: abundances are not finite even after filling missing values")
    if np.any(data < 0.0):
        raise StepError(f"{label}: abundances must be non-negative")
    if data.size == 0:
        raise StepError(f"{label}: abundance table is empty")
    return data, labels_in_order(form, sample_dim), labels_in_order(form, taxon_dim)


def normalize_group(value):
    """Normalize a group label; return None for missing values."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _MISSING:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return text
    if np.isfinite(number) and number == int(number):
        return str(int(number))
    return text


def group_codes(meta, sample_dim: str, group_label: str, samples, label: str) -> np.ndarray:
    """Return the normalized group label of every abundance sample."""
    meta_samples, values = group_values(meta, sample_dim, group_label)
    positions = {name: index for index, name in enumerate(meta_samples)}
    missing = [name for name in samples if name not in positions]
    if missing:
        preview = ", ".join(missing[:5])
        raise StepError(
            f"{label}: {len(missing)} samples have no {group_label!r} value: {preview}"
        )
    codes = [normalize_group(values[positions[name]]) for name in samples]
    bad = [name for name, code in zip(samples, codes) if code is None]
    if bad:
        preview = ", ".join(bad[:5])
        raise StepError(
            f"{label}: {len(bad)} samples have a missing {group_label!r} value: {preview}"
        )
    return np.asarray(codes, dtype=object)


def pairwise(matrix: np.ndarray, method: str, label: str) -> np.ndarray:
    """Pairwise sample distances for the supported community metrics."""
    metrics = {"euclidean": "euclidean", "bray": "braycurtis", "manhattan": "cityblock"}
    if method not in metrics:
        raise StepError(f"{label}: unknown distance {method!r}; use one of {sorted(metrics)}")
    if matrix.shape[0] < 2:
        raise StepError(f"{label}: need at least two samples")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = squareform(pdist(matrix, metric=metrics[method]))
    if not np.all(np.isfinite(out)):
        raise StepError(f"{label}: {method} distance is undefined; check for zero-total samples")
    return out
