"""Small shared helpers for the 0.20 agreement/regression operators."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.steps._ext_common import labels_in_order, reorder, require_dims


def table(form: Form, row_dim: str, col_dim: str, label: str) -> tuple[np.ndarray, list[str], list[str]]:
    require_dims(form, row_dim, col_dim, label=label)
    data = reorder(form, row_dim, col_dim)
    if data.size == 0:
        raise StepError(f"{label}: table is empty")
    if not np.isfinite(data).all():
        raise StepError(f"{label}: table must be finite")
    return data, labels_in_order(form, row_dim), labels_in_order(form, col_dim)


def scalar_form(rows, names, method: str) -> Form:
    names = list(names)
    data = np.asarray(rows, dtype=np.float64).reshape(-1, 1)
    if data.shape[0] != len(names):
        raise StepError("internal error: statistic name/value length mismatch")
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["statistic", "value"],
        labels={"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
        info={"missing_code": np.nan, "method": method},
    )


def distance(form: Form, dim: str, dim_b: str, label: str) -> tuple[np.ndarray, list[str]]:
    require_dims(form, dim, dim_b, label=label)
    if form.data.ndim != 2 or form.data.shape[0] != form.data.shape[1]:
        raise StepError(f"{label}: distance matrix must be square")
    data = np.asarray(form.data, dtype=np.float64)
    if not np.isfinite(data).all():
        raise StepError(f"{label}: distance matrix must be finite")
    if not np.allclose(data, data.T, equal_nan=False):
        raise StepError(f"{label}: distance matrix must be symmetric")
    if dict(form.labels[dim]) != dict(form.labels[dim_b]):
        raise StepError(f"{label}: distance matrix axes must share labels")
    return data, labels_in_order(form, dim)
