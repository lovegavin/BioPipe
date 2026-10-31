"""Shared p-value adjustment implementation for Holm and BY."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def adjust(form, method, feature_dim, value_dim, output, ctx, name):
    if form.data.ndim != 2:
        raise StepError(f"{name} expects a 2D form")
    if feature_dim not in form.dims or value_dim not in form.dims:
        raise StepError(f"{name}: expected {feature_dim!r} and {value_dim!r} in {form.dims}")
    axis = form.dims.index(value_dim)
    values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, 1)
    if values.shape[1] != 1:
        raise StepError(f"{name} expects exactly one p-value column")
    p = values[:, 0]
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise StepError(f"{name}: p-values must be finite and in [0, 1]")
    n = int(len(p))
    order = np.argsort(p, kind="stable")
    ranked = p[order]
    if method == "holm":
        scaled = (n - np.arange(n, dtype=np.float64)) * ranked
        q_sorted = np.maximum.accumulate(scaled)
    elif method == "by":
        harmonic = float(np.sum(1.0 / np.arange(1, n + 1, dtype=np.float64)))
        ranks = np.arange(1, n + 1, dtype=np.float64)
        scaled = ranked * n * harmonic / ranks
        q_sorted = np.minimum.accumulate(scaled[::-1])[::-1]
    else:
        raise StepError(f"{name}: unsupported method {method!r}")
    q = np.empty(n, dtype=np.float64)
    q[order] = np.clip(q_sorted, 0.0, 1.0)
    out = Form(
        data=q.reshape(-1, 1).astype(np.float32),
        dims=[feature_dim, "statistic"],
        labels={feature_dim: dict(form.labels[feature_dim]), "statistic": {"qvalue": 0}},
        info={"missing_code": np.nan, "correction": method, "n_tests": n},
    )
    ctx[ctx.step_params.get("output", output)] = out
    return {"n_tests": n, "method": method, "n_significant_0_05": int((q < 0.05).sum())}
