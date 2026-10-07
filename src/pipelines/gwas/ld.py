# src/pipelines/gwas/ld.py
"""LD pruning: 基于滑窗 r² 的近似独立 SNP 子集"""

import numpy as np


def _r2(x, y):
    valid = (x >= 0) & (y >= 0)
    if valid.sum() < 3:
        return 0.0
    xv = x[valid].astype(float)
    yv = y[valid].astype(float)
    if xv.std() < 1e-8 or yv.std() < 1e-8:
        return 0.0
    r = np.corrcoef(xv, yv)[0, 1]
    if not np.isfinite(r):
        return 0.0
    return float(r * r)


def prune_by_ld(dosage, r2_threshold=0.2, window=50):
    """
    返回: keep_mask (n_snps,) bool
    """
    n_snps = dosage.shape[0]
    keep = np.ones(n_snps, dtype=bool)

    for i in range(n_snps):
        if not keep[i]:
            continue
        upper = min(i + window + 1, n_snps)
        for j in range(i + 1, upper):
            if not keep[j]:
                continue
            if _r2(dosage[i], dosage[j]) > r2_threshold:
                keep[j] = False

    n_kept = int(keep.sum())
    print(f"LD pruning: {n_snps} → {n_kept} SNP "
          f"(r²>{r2_threshold}, 窗口={window})")
    return keep