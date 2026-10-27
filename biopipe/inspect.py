"""Bounded, JSON-friendly inspection of an input file for route authoring."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.reader import pick_reader, read_source


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def inspect_source(path: Path, reader_name: str | None = None, args: dict | None = None) -> dict:
    """Read a source with the normal Reader, then return shape/label/statistics.

    This is intentionally a full read: it is meant for route authoring on the
    actual input, not for huge production files. Use ``--reader`` to override
    extension dispatch and ``--arg key=value`` for Reader options.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"input file not found: {path}")
    args = dict(args or {})
    reader = pick_reader(path, name=reader_name)
    template = reader.file_input or {}
    dims = list(template.get("dims") or ["row", "column"])
    labels = dict(template.get("labels") or {d: "builtin" for d in dims})
    form = read_source(path, dims, labels, reader=reader_name, **args)
    data = form.data
    finite = np.isfinite(data) if np.issubdtype(data.dtype, np.number) else np.ones(data.shape, bool)
    values = data[finite]
    labels_summary = {
        dim: {
            "count": len(mapping),
            "first": list(mapping)[:8],
        }
        for dim, mapping in form.labels.items()
    }
    encoders = {
        dim: {field: f"{type(encoder).__name__}" for field, encoder in fields.items()}
        for dim, fields in (form.info.get("encoders") or {}).items()
    }
    info = {key: value for key, value in form.info.items() if key != "encoders"}
    head = data[:3, :3]
    return {
        "path": str(path),
        "file_bytes": path.stat().st_size,
        "reader": type(reader).__name__,
        "dims": list(form.dims),
        "shape": list(data.shape),
        "dtype": str(data.dtype),
        "labels": labels_summary,
        "info": _jsonable(info),
        "encoders": encoders,
        "stats": {
            "n_cells": int(data.size),
            "n_finite": int(finite.sum()),
            "n_missing": int((~finite).sum()),
            "min": _jsonable(float(values.min())) if values.size else None,
            "max": _jsonable(float(values.max())) if values.size else None,
            "mean": _jsonable(float(values.mean())) if values.size else None,
        },
        "head": _jsonable(head),
        "suggested": {"dims": list(form.dims), "labels": labels},
    }
