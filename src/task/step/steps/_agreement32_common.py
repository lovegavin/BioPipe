"""Shared helpers for 0.32 agreement and reliability operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.steps._stats21_common import numeric_column, table_frame


def paired_columns(form, sample_dim: str, feature_dim: str, method_a: str, method_b: str, label: str):
    frame = table_frame(form, sample_dim, feature_dim, label)
    x = numeric_column(frame, method_a, label)
    y = numeric_column(frame, method_b, label)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    if x.size < 3:
        raise StepError(f"{label}: need at least three complete pairs")
    if np.std(x) == 0 or np.std(y) == 0:
        raise StepError(f"{label}: both measurement columns must vary")
    return x, y


def icc_from_matrix(ratings: np.ndarray, model: str, kind: str, unit: str, confidence: float):
    """Port of irr::icc formulas for one-way/two-way ICC(A,1/C,1/A,k/C,k)."""
    ratings = np.asarray(ratings, dtype=np.float64)
    n, k = ratings.shape
    if n < 2 or k < 2:
        raise StepError("intraclass_correlation: need at least two subjects and two raters")
    if not np.isfinite(ratings).all():
        raise StepError("intraclass_correlation: ratings must be finite")
    if np.any(np.var(ratings, axis=0, ddof=1) == 0):
        raise StepError("intraclass_correlation: every rater must vary")

    total = np.var(ratings.ravel(), ddof=1) * (n * k - 1)
    msr = np.var(np.mean(ratings, axis=1), ddof=1) * k
    msw = np.mean(np.var(ratings, axis=1, ddof=1))
    msc = np.var(np.mean(ratings, axis=0), ddof=1) * n
    mse = (total - msr * (n - 1) - msc * (k - 1)) / ((n - 1) * (k - 1))
    alpha = 1.0 - confidence

    if unit == "single":
        if model == "oneway":
            value = (msr - msw) / (msr + (k - 1) * msw)
            f_value = msr / msw
            df1, df2 = n - 1, n * (k - 1)
            p_value = float(stats_f_sf(f_value, df1, df2))
            fl = (msr / msw) / stats_f_ppf(1 - alpha / 2, n - 1, n * (k - 1))
            fu = (msr / msw) * stats_f_ppf(1 - alpha / 2, n * (k - 1), n - 1)
            lo = (fl - 1) / (fl + k - 1)
            hi = (fu - 1) / (fu + k - 1)
        elif kind == "consistency":
            value = (msr - mse) / (msr + (k - 1) * mse)
            f_value = msr / mse
            df1, df2 = n - 1, (n - 1) * (k - 1)
            p_value = float(stats_f_sf(f_value, df1, df2))
            fl = (msr / mse) / stats_f_ppf(1 - alpha / 2, n - 1, (n - 1) * (k - 1))
            fu = (msr / mse) * stats_f_ppf(1 - alpha / 2, (n - 1) * (k - 1), n - 1)
            lo = (fl - 1) / (fl + k - 1)
            hi = (fu - 1) / (fu + k - 1)
        else:
            value = (msr - mse) / (msr + (k - 1) * mse + (k / n) * (msc - mse))
            a = (k * 0.0) / (n * 1.0)
            b = 1.0
            v = (a * msc + b * mse) ** 2 / (
                (a * msc) ** 2 / (k - 1) + (b * mse) ** 2 / ((n - 1) * (k - 1))
            )
            f_value = msr / (a * msc + b * mse)
            df1, df2 = n - 1, v
            p_value = float(stats_f_sf(f_value, df1, df2))
            a = (k * value) / (n * (1 - value))
            b = 1 + (k * value * (n - 1)) / (n * (1 - value))
            v = (a * msc + b * mse) ** 2 / (
                (a * msc) ** 2 / (k - 1) + (b * mse) ** 2 / ((n - 1) * (k - 1))
            )
            fl = stats_f_ppf(1 - alpha / 2, n - 1, v)
            fu = stats_f_ppf(1 - alpha / 2, v, n - 1)
            lo = (n * (msr - fl * mse)) / (
                fl * (k * msc + (k * n - k - n) * mse) + n * msr
            )
            hi = (n * (fu * msr - mse)) / (
                k * msc + (k * n - k - n) * mse + n * fu * msr
            )
    else:
        if model == "oneway":
            value = (msr - msw) / msr
            f_value = msr / msw
            df1, df2 = n - 1, n * (k - 1)
            p_value = float(stats_f_sf(f_value, df1, df2))
            fl = (msr / msw) / stats_f_ppf(1 - alpha / 2, n - 1, n * (k - 1))
            fu = (msr / msw) * stats_f_ppf(1 - alpha / 2, n * (k - 1), n - 1)
            lo, hi = 1 - 1 / fl, 1 - 1 / fu
        elif kind == "consistency":
            value = (msr - mse) / msr
            f_value = msr / mse
            df1, df2 = n - 1, (n - 1) * (k - 1)
            p_value = float(stats_f_sf(f_value, df1, df2))
            fl = (msr / mse) / stats_f_ppf(1 - alpha / 2, n - 1, (n - 1) * (k - 1))
            fu = (msr / mse) * stats_f_ppf(1 - alpha / 2, (n - 1) * (k - 1), n - 1)
            lo, hi = 1 - 1 / fl, 1 - 1 / fu
        else:
            value = (msr - mse) / (msr + (msc - mse) / n)
            a = 0.0
            b = 1.0
            v = (a * msc + b * mse) ** 2 / (
                (a * msc) ** 2 / (k - 1) + (b * mse) ** 2 / ((n - 1) * (k - 1))
            )
            f_value = msr / (a * msc + b * mse)
            df1, df2 = n - 1, v
            p_value = float(stats_f_sf(f_value, df1, df2))
            a = (k * value) / (n * (1 - value))
            b = 1 + (k * value * (n - 1)) / (n * (1 - value))
            v = (a * msc + b * mse) ** 2 / (
                (a * msc) ** 2 / (k - 1) + (b * mse) ** 2 / ((n - 1) * (k - 1))
            )
            fl = stats_f_ppf(1 - alpha / 2, n - 1, v)
            fu = stats_f_ppf(1 - alpha / 2, v, n - 1)
            lo = (n * (msr - fl * mse)) / (fl * (msc - mse) + n * msr)
            hi = (n * (fu * msr - mse)) / (msc - mse + n * fu * msr)
    return {
        "subjects": float(n), "raters": float(k), "icc": float(value),
        "f": float(f_value), "df1": float(df1), "df2": float(df2),
        "p": float(p_value), "ci_low": float(lo), "ci_high": float(hi),
        "msr": float(msr), "msc": float(msc), "mse": float(mse),
        "model": model, "type": kind if model == "twoway" else "oneway",
        "unit": unit, "confidence": float(confidence),
    }


def stats_f_sf(value, df1, df2):
    from scipy import stats
    return stats.f.sf(value, df1, df2)


def stats_f_ppf(value, df1, df2):
    from scipy import stats
    return stats.f.ppf(value, df1, df2)
