"""Shared helpers for the 0.30 regression extensions."""
from __future__ import annotations

import numpy as np

from src.core import StepError


def drop_intercept(design, terms):
    """Remove the leading constant column from a design matrix."""
    if terms and terms[0] == "Intercept":
        return design[:, 1:], terms[1:]
    return design, terms


def coefficient_rows(params, bse, pvalues, conf, terms, ratios: bool = False):
    """Pack coefficients into long statistic rows."""
    rows = []
    for i, _term in enumerate(terms):
        coef = float(params[i])
        se = float(bse[i])
        z = coef / se if np.isfinite(se) and se > 0 else float("nan")
        p = float(pvalues[i])
        low, high = float(conf[i, 0]), float(conf[i, 1])
        row = [coef, se, z, p, low, high]
        if ratios:
            row.extend([float(np.exp(coef)), float(np.exp(low)), float(np.exp(high))])
        rows.append(row)
    return rows


def require_binary(values, label: str) -> np.ndarray:
    """Return a 0/1 array or raise a readable error."""
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isin(array, [0.0, 1.0])):
        raise StepError(f"{label}: event column must contain only 0/1")
    return array.astype(np.int64)
