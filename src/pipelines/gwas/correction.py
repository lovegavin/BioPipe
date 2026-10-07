# src/pipelines/gwas/correction.py
"""多重假设校正 + λGC 计算"""

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

CHI2_MEDIAN = 0.4549364


def compute_lambda_gc(p_values):
    p = np.asarray(p_values)
    p = p[np.isfinite(p) & (p > 0) & (p <= 1)]
    if p.size == 0:
        return float("nan")
    chi2 = stats.chi2.isf(p, df=1)
    return float(np.median(chi2) / CHI2_MEDIAN)


def apply_correction(results, method="bonferroni", fdr_threshold=0.05):
    """
    返回: (df, meta)
    - Bonferroni: 新增 SIGNIFICANT 列, 不加 Q_VALUE
    - FDR:        新增 SIGNIFICANT + Q_VALUE 列
    - method=None: 新增 SIGNIFICANT 列全 False
    """
    df = results.copy()
    pvals = df["P"].values
    valid = np.isfinite(pvals)
    n_tests = int(valid.sum())

    lambda_gc = compute_lambda_gc(pvals)
    meta = {"method": method, "n_tests": n_tests, "lambda_gc": lambda_gc}

    if method is None:
        df["SIGNIFICANT"] = False
        meta["threshold"] = None
        meta["n_significant"] = 0
        return df, meta

    if method == "bonferroni":
        threshold = 0.05 / max(n_tests, 1)
        df["SIGNIFICANT"] = valid & (pvals < threshold)
        meta["threshold"] = float(threshold)
        # 不加 Q_VALUE 列

    elif method == "fdr":
        q = np.full(len(pvals), np.nan)
        if n_tests > 0:
            _, q_valid, _, _ = multipletests(pvals[valid], method="fdr_bh")
            q[valid] = q_valid
        df["Q_VALUE"] = q
        df["SIGNIFICANT"] = q < fdr_threshold
        meta["threshold"] = float(fdr_threshold)

    else:
        raise ValueError(f"未知校正方法: {method}")

    meta["n_significant"] = int(df["SIGNIFICANT"].sum())
    print(f"校正 ({method}): λGC={lambda_gc:.3f}, "
          f"阈值={meta['threshold']:.2e}, 显著 SNP={meta['n_significant']}")

    return df, meta