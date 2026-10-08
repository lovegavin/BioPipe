# src/pipelines/gwas/models/firth.py
"""Firth penalized logistic regression.

Reference
---------
Firth D (1993). Bias reduction of maximum likelihood estimates.
Biometrika 80(1):27-38.
"""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from scipy import stats
from scipy.optimize import minimize


def fit_firth(
    y: np.ndarray,
    X: np.ndarray,
    max_iter: int = 50,
    ftol: float = 1e-7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Fit Firth-penalized logistic regression.

    Parameters
    ----------
    y : np.ndarray
        Binary response, shape ``(n,)``.
    X : np.ndarray
        Design matrix ``[intercept, dosage, covariates...]``.

    Returns
    -------
    (beta, se, pvalues) or None on failure.
    """
    n, p = X.shape
    y = y.astype(float)

    # Logistic initial values for fast convergence.
    try:
        init = sm.Logit(y, X).fit(disp=0, maxiter=50)
        beta0 = np.asarray(init.params, dtype=float)
        if not np.all(np.isfinite(beta0)):
            beta0 = np.zeros(p)
    except Exception:
        beta0 = np.zeros(p)

    def neg_penalized_loglik(beta: np.ndarray) -> float:
        eta = np.clip(X @ beta, -30.0, 30.0)
        loglik = float(np.sum(y * eta - np.log1p(np.exp(eta))))
        p_hat = 1.0 / (1.0 + np.exp(-eta))
        w = p_hat * (1.0 - p_hat)
        fisher = X.T @ (X * w[:, None])
        sign, logdet = np.linalg.slogdet(fisher)
        if sign <= 0 or not np.isfinite(logdet):
            return 1e10
        return -(loglik + 0.5 * logdet)

    try:
        res = minimize(
            neg_penalized_loglik,
            beta0,
            method="L-BFGS-B",
            options={"maxiter": max_iter, "ftol": ftol},
        )
    except Exception:
        return None

    if not res.success or not np.all(np.isfinite(res.x)):
        return None

    beta = res.x
    eta = np.clip(X @ beta, -30.0, 30.0)
    p_hat = 1.0 / (1.0 + np.exp(-eta))
    w = p_hat * (1.0 - p_hat)
    fisher = X.T @ (X * w[:, None])

    try:
        cov = np.linalg.inv(fisher)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(fisher)

    diag = np.diag(cov)
    if np.any(diag <= 0):
        return None
    se = np.sqrt(diag)

    with np.errstate(divide="ignore", invalid="ignore"):
        z = beta / se
        pvals = 2.0 * (1.0 - stats.norm.cdf(np.abs(z)))

    if not np.all(np.isfinite(pvals)):
        return None

    return beta, se, pvals