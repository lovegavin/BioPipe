"""Small shared helpers for projection and group-test operators."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from ._ext_common import group_map


def matrix(form: Form, sample_dim: str, feature_dim: str):
    if form.data.ndim != 2:
        raise StepError(f"expected a 2D form, got ndim={form.data.ndim}")
    if sample_dim not in form.dims or feature_dim not in form.dims:
        raise StepError(
            f"expected dims {sample_dim!r} and {feature_dim!r}, got {form.dims}"
        )
    axis = form.dims.index(sample_dim)
    X = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
    if X.shape[0] < 2 or X.shape[1] < 1:
        raise StepError("need at least two samples and one feature")
    col_mean = np.nanmean(X, axis=0)
    col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
    X = np.where(np.isfinite(X), X, col_mean)
    samples = _ordered(form.labels[sample_dim])
    features = _ordered(form.labels[feature_dim])
    return X, samples, features


def _ordered(labels: dict) -> list[str]:
    return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]


def projection(ctx, out_name: str, X, sample_dim: str, samples, prefix: str):
    data = np.asarray(X, dtype=np.float32)
    ctx[out_name] = Form(
        data=data,
        dims=[sample_dim, "component"],
        labels={
            sample_dim: {name: i for i, name in enumerate(samples)},
            "component": {f"{prefix}{i + 1}": i for i in range(data.shape[1])},
        },
        info={"missing_code": np.nan},
    )


def grouped(form, meta, sample_dim, feature_dim, group_dim, group_label):
    X, samples, features = matrix(form, sample_dim, feature_dim)
    meta_samples, codes = group_map(meta, group_dim, group_label)
    meta_pos = {name: i for i, name in enumerate(meta_samples)}
    keep = [i for i, name in enumerate(samples) if name in meta_pos]
    if len(keep) < 4:
        raise StepError(f"only {len(keep)} shared samples between data and metadata")
    X = X[keep]
    codes = codes[[meta_pos[samples[i]] for i in keep]]
    groups = sorted(set(int(c) for c in codes))
    if len(groups) < 2:
        raise StepError("need at least two groups")
    columns = []
    for g in groups:
        mask = codes == g
        if int(mask.sum()) < 2:
            raise StepError(f"group {g} has fewer than two samples")
        columns.append(X[mask])
    return columns, features, groups
