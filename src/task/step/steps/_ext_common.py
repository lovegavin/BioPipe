"""Shared helpers for the extension operators.

These are intentionally small: axis alignment, statistical corrections and
Form construction only. Individual operators keep their own math and docs.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.reader.readers._labels import unique_labels


def require_dims(form: Form, *names: str, label: str) -> None:
    if form.data.ndim != 2:
        raise StepError(f"{label} must be 2D, got ndim={form.data.ndim}")
    for name in names:
        if name not in form.dims:
            raise StepError(f"{label}: dim {name!r} not in {form.dims}")


def reorder(form: Form, first: str, second: str) -> np.ndarray:
    """Return a 2D array ordered as [first, second]."""
    require_dims(form, first, second, label="input")
    data = np.asarray(form.data, dtype=np.float64)
    if form.dims.index(first) == 1:
        data = data.T
    return data


def labels_in_order(form: Form, dim: str) -> list[str]:
    return [label for label, _ in sorted(form.labels[dim].items(), key=lambda item: item[1])]


def correct(pvalues, method: str = "fdr"):
    from statsmodels.stats.multitest import multipletests
    mapping = {"fdr": "fdr_bh", "bonferroni": "bonferroni", "holm": "holm", "hommel": "hommel", "fdr_by": "fdr_by"}
    if method not in mapping:
        raise StepError(f"unknown correction {method!r}")
    values = np.asarray(pvalues, dtype=np.float64)
    if values.size == 0:
        return values
    result = np.full(values.shape, np.nan, dtype=np.float64)
    finite = np.isfinite(values)
    if finite.any():
        result[finite] = multipletests(values[finite], method=mapping[method])[1]
    return result


def normal_p(z):
    return np.clip(2.0 * stats.norm.sf(np.abs(z)), 0.0, 1.0)


def make_form(data, dims, labels, info=None):
    form = Form(data=np.asarray(data, dtype=np.float32), dims=list(dims), labels=labels,
                info={"missing_code": np.nan, **(info or {})})
    form.validate()
    return form


def axis_labels(names, dim):
    return unique_labels(names, dim, "extension")


def group_values(meta: Form, sample_dim: str, group_label: str) -> tuple[list[str], np.ndarray]:
    """Return sample labels and group values from a metadata Form.

    Metadata is normally [sample, feature]; a group column is a feature
    label whose values live in the data matrix. A direct sample-axis label
    is also accepted for simple lookup-style Forms.
    """
    require_dims(meta, sample_dim, label="metadata")
    values = meta.get_parallel(group_label, sample_dim)
    if values is None:
        other = next((dim for dim in meta.dims if dim != sample_dim), None)
        if other is None or group_label not in meta.labels.get(other, {}):
            raise StepError(f"metadata: group column {group_label!r} not found")
        data = np.asarray(meta.data, dtype=object)
        if meta.dims.index(sample_dim) == 1:
            data = data.T
        values = data[:, meta.labels[other][group_label]]
        encoder = meta.info.get("encoders", {}).get(other, {}).get(group_label)
        if encoder is not None and hasattr(encoder, "inverse_transform"):
            values = np.asarray(values, dtype=np.int64)
            values = encoder.inverse_transform(values)
    samples = labels_in_order(meta, sample_dim)
    values = np.asarray(values)
    if values.ndim != 1 or len(values) != len(samples):
        raise StepError(f"metadata: group column {group_label!r} is not parallel to {sample_dim!r}")
    return samples, values


def group_map(meta: Form, sample_dim: str, group_label: str) -> tuple[list[str], np.ndarray]:
    """Return sample labels and integer group codes in the metadata's sample order."""
    samples, values = group_values(meta, sample_dim, group_label)
    codes = {}
    encoded = []
    for value in values:
        key = str(value)
        if key not in codes:
            codes[key] = len(codes)
        encoded.append(codes[key])
    return samples, np.asarray(encoded, dtype=np.int64)
