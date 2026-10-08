# src/pipelines/gwas/models/ols.py
"""Ordinary least squares for continuous traits."""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm


def fit_ols(y: np.ndarray, X: np.ndarray) -> tuple[float, float, float] | None:
    """Fit OLS and return the coefficient of the second design column.

    The design matrix is expected to be ``[intercept, dosage, covariates...]``.
    ``params[1]`` is the effect size of the dosage term.

    Returns
    -------
    (beta, se, pvalue) or None on failure.
    """
    try:
        model = sm.OLS(y, X).fit()
    except Exception:
        return None
    beta = float(model.params[1])
    se = float(model.bse[1])
    pval = float(model.pvalues[1])
    if not (np.isfinite(beta) and np.isfinite(se) and np.isfinite(pval)):
        return None
    return beta, se, pval