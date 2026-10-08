# src/pipelines/gwas/models/logit.py
"""Standard logistic regression."""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm


def fit_logit(y: np.ndarray, X: np.ndarray) -> tuple[float, float, float] | None:
    """Fit logistic regression and return the dosage coefficient."""
    try:
        model = sm.Logit(y, X).fit(disp=0, maxiter=200)
    except Exception:
        return None
    beta = float(model.params[1])
    se = float(model.bse[1])
    pval = float(model.pvalues[1])
    if not (np.isfinite(beta) and np.isfinite(se) and np.isfinite(pval)):
        return None
    return beta, se, pval