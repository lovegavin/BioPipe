"""Shared helpers for 2x2 epidemiological effect sizes."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError


def count_table(form, row_dim: str, col_dim: str, label: str) -> np.ndarray:
    """Return a 2x2 float64 table ordered as [row, column]."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: input must be 2D")
    if row_dim not in form.dims or col_dim not in form.dims:
        raise StepError(f"{label}: expected dims {row_dim!r}, {col_dim!r}, got {form.dims}")
    data = np.asarray(form.data, dtype=np.float64)
    if form.dims.index(row_dim) != 0:
        data = data.T
    if data.shape != (2, 2):
        raise StepError(f"{label}: needs a 2x2 table, got {data.shape}")
    if not np.isfinite(data).all():
        raise StepError(f"{label}: table contains non-finite values")
    if (data < 0).any():
        raise StepError(f"{label}: counts must be non-negative")
    return data


def corrected_table(table: np.ndarray, correction: str, label: str) -> tuple[np.ndarray, bool]:
    """Apply the Haldane-Anscombe correction when requested and needed."""
    if correction not in {"none", "haldane"}:
        raise StepError(f"{label}: correction must be 'none' or 'haldane'")
    used = correction == "haldane" and bool((table == 0).any())
    if used:
        table = table + 0.5
    if (table <= 0).any():
        raise StepError(
            f"{label}: all four cells must be positive; "
            "use correction='haldane' for zero cells"
        )
    return table, used


def normal_quantile(confidence: float, label: str) -> float:
    if not 0.0 < confidence < 1.0:
        raise StepError(f"{label}: confidence must be between 0 and 1")
    return float(stats.norm.ppf(0.5 + confidence / 2.0))


def risk_ratio(table: np.ndarray, confidence: float) -> dict[str, float]:
    a, b = float(table[0, 0]), float(table[0, 1])
    c, d = float(table[1, 0]), float(table[1, 1])
    n1, n2 = a + b, c + d
    p1, p2 = a / n1, c / n2
    rr = p1 / p2
    se = float(np.sqrt(1.0 / a - 1.0 / n1 + 1.0 / c - 1.0 / n2))
    z = normal_quantile(confidence, "risk_ratio")
    return {
        "rr": float(rr),
        "ci_lower": float(np.exp(np.log(rr) - z * se)),
        "ci_upper": float(np.exp(np.log(rr) + z * se)),
        "p1": float(p1),
        "p2": float(p2),
        "n": float(n1 + n2),
        "se": float(se),
    }


def odds_ratio(table: np.ndarray, confidence: float) -> dict[str, float]:
    a, b = float(table[0, 0]), float(table[0, 1])
    c, d = float(table[1, 0]), float(table[1, 1])
    odds = a * d / (b * c)
    se = float(np.sqrt(1.0 / a + 1.0 / b + 1.0 / c + 1.0 / d))
    z = normal_quantile(confidence, "odds_ratio")
    return {
        "odds_ratio": float(odds),
        "ci_lower": float(np.exp(np.log(odds) - z * se)),
        "ci_upper": float(np.exp(np.log(odds) + z * se)),
        "log_or": float(np.log(odds)),
        "se": se,
        "n": float(a + b + c + d),
    }


def cohens_h(table: np.ndarray, confidence: float) -> dict[str, float]:
    a, b = float(table[0, 0]), float(table[0, 1])
    c, d = float(table[1, 0]), float(table[1, 1])
    n1, n2 = a + b, c + d
    if n1 <= 0 or n2 <= 0:
        raise StepError("cohens_h: each row must contain at least one observation")
    p1, p2 = a / n1, c / n2
    h = 2.0 * np.arcsin(np.sqrt(p1)) - 2.0 * np.arcsin(np.sqrt(p2))
    se = float(np.sqrt(1.0 / n1 + 1.0 / n2))
    z = normal_quantile(confidence, "cohens_h")
    return {
        "h": float(h),
        "ci_lower": float(h - z * se),
        "ci_upper": float(h + z * se),
        "p1": float(p1),
        "p2": float(p2),
        "n1": float(n1),
        "n2": float(n2),
    }
