# src/pipelines/gwas/firth.py
"""Firth 惩罚逻辑回归"""

import numpy as np
import statsmodels.api as sm
from scipy import stats
from scipy.optimize import minimize


def fit_firth(y, X, max_iter=50, ftol=1e-7):
    """
    Firth 惩罚逻辑回归。
    用 Logit 做初值加速, 放宽收敛条件。
    """
    n, p = X.shape
    y = y.astype(float)

    # ---- Logit 初值 ----
    try:
        init_model = sm.Logit(y, X).fit(disp=0, maxiter=50)
        beta0 = np.asarray(init_model.params, dtype=float)
        if not np.all(np.isfinite(beta0)):
            beta0 = np.zeros(p)
    except Exception:
        beta0 = np.zeros(p)

    # ---- 目标函数 ----
    def neg_pen_loglik(beta):
        eta = np.clip(X @ beta, -30.0, 30.0)
        # log-likelihood
        ll = float(np.sum(y * eta - np.log1p(np.exp(eta))))
        # Fisher information
        p_hat = 1.0 / (1.0 + np.exp(-eta))
        w = p_hat * (1.0 - p_hat)
        XtWX = X.T @ (X * w[:, None])
        sign, logdet = np.linalg.slogdet(XtWX)
        if sign <= 0 or not np.isfinite(logdet):
            return 1e10
        return -(ll + 0.5 * logdet)

    # ---- 优化 ----
    try:
        res = minimize(
            neg_pen_loglik, beta0, method="L-BFGS-B",
            options={"maxiter": max_iter, "ftol": ftol},
        )
    except Exception:
        return None

    if not res.success or not np.all(np.isfinite(res.x)):
        return None

    beta = res.x

    # ---- 标准误 ----
    eta = np.clip(X @ beta, -30.0, 30.0)
    p_hat = 1.0 / (1.0 + np.exp(-eta))
    w = p_hat * (1.0 - p_hat)
    XtWX = X.T @ (X * w[:, None])
    try:
        cov = np.linalg.inv(XtWX)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(XtWX)

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