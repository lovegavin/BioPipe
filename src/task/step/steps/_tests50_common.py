"""Shared alignment helpers for the 0.50 group tests."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from ._ext_common import group_values, labels_in_order, require_dims


def expression_matrix(form: Form, sample_dim: str, feature_dim: str):
    """Return [sample, feature] values without imputing missing cells."""
    require_dims(form, sample_dim, feature_dim, label="expression")
    X = np.moveaxis(
        np.asarray(form.data, dtype=np.float64),
        form.dims.index(sample_dim),
        0,
    )
    samples = labels_in_order(form, sample_dim)
    features = labels_in_order(form, feature_dim)
    if X.shape != (len(samples), len(features)):
        raise StepError(
            "expression: labels do not match the data shape "
            f"({X.shape[0]} samples, {X.shape[1]} features)"
        )
    return X, samples, features


def grouped_expression(
    expression: Form,
    meta: Form,
    sample_dim: str,
    feature_dim: str,
    group_dim: str,
    group_label: str,
):
    """Align an expression table with one group value per sample."""
    X, samples, features = expression_matrix(expression, sample_dim, feature_dim)
    meta_samples, values = group_values(meta, group_dim, group_label)
    lookup = {str(sample): str(value) for sample, value in zip(meta_samples, values)}
    keep = [i for i, sample in enumerate(samples) if sample in lookup]
    if len(keep) < 4:
        raise StepError(f"only {len(keep)} shared samples between expression and metadata")
    X = X[keep]
    kept = [samples[i] for i in keep]
    groups = [lookup[sample] for sample in kept]
    labels = sorted(set(groups))
    if len(labels) < 2:
        raise StepError("need at least two groups")
    for label in labels:
        if groups.count(label) < 2:
            raise StepError(f"group {label!r} has fewer than two samples")
    return X, features, kept, groups, labels
