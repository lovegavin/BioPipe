"""Shared helpers for genomic interval operators (BED-like forms)."""
from __future__ import annotations

import numpy as np

from src.core import StepError


def _decode(values, encoder):
    if encoder is None:
        return [str(v) for v in values]
    inverse = getattr(encoder, "inverse", {})
    return [str(inverse.get(int(v), v)) for v in values]


def column(form, field_dim, name, operator, required=True):
    labels = form.labels.get(field_dim, {})
    if name not in labels:
        if required:
            raise StepError(f"{operator}: field '{name}' is required")
        return None
    index = labels[name]
    return np.asarray(form.data[:, index], dtype=float)


def interval_table(
    form,
    region_dim,
    field_dim,
    chrom_field,
    start_field,
    end_field,
    operator,
    class_field=None,
    class_names=None,
):
    """Decode a BED-like form into per-chromosome interval arrays.

    Returns ``(regions, classes, totals)`` where ``regions[chrom]`` is a dict
    with sorted ``starts``/``ends`` arrays and ``classes[chrom]`` holds a
    per-interval integer class index (-1 when absent).
    """
    if len(form.dims) != 2:
        raise StepError(f"{operator}: interval input must be two-dimensional")
    chrom = column(form, field_dim, chrom_field, operator)
    start = column(form, field_dim, start_field, operator)
    end = column(form, field_dim, end_field, operator)
    if start is None or end is None:
        raise StepError(f"{operator}: start/end columns are required")
    if start.shape != end.shape or start.shape[0] != form.data.shape[0]:
        raise StepError(f"{operator}: start/end columns are not parallel")
    if np.any(~np.isfinite(start)) or np.any(~np.isfinite(end)):
        raise StepError(f"{operator}: interval coordinates must be finite")
    if np.any(start < 0) or np.any(end < start):
        raise StepError(f"{operator}: intervals must satisfy 0 <= start <= end")
    fields = (form.info or {}).get("encoders", {}).get(field_dim, {}) or {}
    encoder = fields.get(chrom_field) if isinstance(fields, dict) else None
    chrom_values = _decode(chrom, encoder)
    class_values = [-1] * form.data.shape[0]
    if class_field is not None:
        if class_field not in (form.labels.get(field_dim) or {}):
            raise StepError(f"{operator}: class column '{class_field}' is required")
        index = form.labels[field_dim][class_field]
        encoded = np.asarray(form.data[:, index], dtype=float)
        class_encoder = fields.get(class_field) if isinstance(fields, dict) else None
        decoded = _decode(encoded, class_encoder)
        lookup = {name: position for position, name in enumerate(class_names or [])}
        unknown = sorted({value for value in decoded if value not in lookup})
        if unknown:
            raise StepError(
                f"{operator}: unknown classes {unknown}; expected {sorted(lookup)}"
            )
        class_values = [lookup[value] for value in decoded]

    grouped = {}
    for i, name in enumerate(chrom_values):
        grouped.setdefault(name, []).append(i)
    regions = {}
    classes = {}
    totals = {}
    for name, indices in grouped.items():
        order = sorted(indices, key=lambda i: (start[i], end[i]))
        starts = np.asarray([start[i] for i in order], dtype=np.int64)
        ends = np.asarray([end[i] for i in order], dtype=np.int64)
        regions[name] = {"starts": starts, "ends": ends, "order": order}
        classes[name] = np.asarray([class_values[i] for i in order], dtype=np.int64)
        totals[name] = int(np.sum(ends - starts))
    return (
        regions,
        classes,
        totals,
        chrom_values,
        np.asarray(start, dtype=np.int64),
        np.asarray(end, dtype=np.int64),
        class_values,
    )


def merge_intervals(starts, ends):
    """Merge sorted half-open intervals, returning (starts, ends)."""
    if len(starts) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    out_starts = [int(starts[0])]
    out_ends = [int(ends[0])]
    for start, end in zip(starts[1:], ends[1:]):
        if start <= out_ends[-1]:
            if end > out_ends[-1]:
                out_ends[-1] = int(end)
        else:
            out_starts.append(int(start))
            out_ends.append(int(end))
    return np.asarray(out_starts, dtype=np.int64), np.asarray(out_ends, dtype=np.int64)


def overlap_bp(a_starts, a_ends, b_starts, b_ends):
    """Total overlap in bp between two sorted interval sets on one chromosome."""
    i = j = 0
    total = 0
    while i < len(a_starts) and j < len(b_starts):
        lo = max(a_starts[i], b_starts[j])
        hi = min(a_ends[i], b_ends[j])
        if hi > lo:
            total += int(hi - lo)
        if a_ends[i] <= b_ends[j]:
            i += 1
        else:
            j += 1
    return total


def coverage_bp(feature_starts, feature_ends, query_starts, query_ends):
    """Covered feature bp for each feature, using a sorted query walk."""
    covered = np.zeros(len(feature_starts), dtype=np.int64)
    j = 0
    n = len(query_starts)
    for i in range(len(feature_starts)):
        start, end = int(feature_starts[i]), int(feature_ends[i])
        while j < n and query_ends[j] <= start:
            j += 1
        k = j
        while k < n and query_starts[k] < end:
            lo = max(start, int(query_starts[k]))
            hi = min(end, int(query_ends[k]))
            if hi > lo:
                covered[i] += hi - lo
            k += 1
    return covered
