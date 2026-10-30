"""Shared label/score extraction for metric operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError


def _column(form, sample_dim, value_dim, column_name, label, dtype):
    if form.data.ndim != 2:
        raise StepError(f"{label}: input must be 2D")
    if sample_dim not in form.dims or value_dim not in form.dims:
        raise StepError(f"{label}: expected dims {sample_dim!r}, {value_dim!r}, got {form.dims}")
    labels = form.labels[value_dim]
    if column_name not in labels:
        raise StepError(f"{label}: {column_name!r} not in {sorted(labels)}")
    axis = form.dims.index(sample_dim)
    data = np.asarray(form.data)
    if axis != 0:
        data = data.T
    samples = [k for k, _ in sorted(form.labels[sample_dim].items(), key=lambda kv: kv[1])]
    values = data[[form.labels[sample_dim][s] for s in samples], labels[column_name]]
    return samples, np.asarray(values, dtype=dtype)


def label_series(form, sample_dim, label_dim, label_name, label):
    samples, raw = _column(form, sample_dim, label_dim, label_name, label, object)
    enc = form.info.get("encoders", {}).get(label_dim, {}).get(label_name)
    out = []
    for value in raw:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            out.append(str(value))
            continue
        if enc is not None and np.isfinite(numeric):
            out.append(str(enc.inverse.get(int(round(numeric)), numeric)))
        else:
            out.append(str(int(round(numeric))) if np.isfinite(numeric) else None)
    return samples, out


def score_series(form, sample_dim, score_dim, score_name):
    samples, values = _column(form, sample_dim, score_dim, score_name, "score", np.float64)
    return samples, values


def shared(labels, scores):
    out = []
    for i, name in enumerate(scores):
        if name in labels:
            out.append((i, labels[name]))
    return out


def binary_truth(samples, labels, positive):
    classes = sorted(set(v for v in labels if v is not None))
    if len(classes) != 2:
        raise StepError(f"need exactly two classes, got {classes}")
    if positive is None:
        positive = classes[-1]
    if positive not in classes:
        raise StepError(f"positive class {positive!r} not in {classes}")
    return classes, positive, np.asarray([1 if v == positive else 0 for v in labels], dtype=np.int64)
