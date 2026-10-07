# src/pipelines/gwas/clump.py
"""LD Clumping: 显著 SNP 去冗余"""

import numpy as np
import pandas as pd

from src.pipelines.gwas.ld import _r2


def _chrom_to_int(c):
    try:
        return int(str(c).replace("chr", ""))
    except ValueError:
        return -1


def clump(results, dosage, r2_thresh=0.5, window_kb=500):
    """
    输入:
        results: DataFrame 含 SIGNIFICANT / P / CHROM / POS / ID
                 行序与 dosage 一致 (均经同一 QC 过滤)
        dosage:  (n_snps, n_samples)
    返回: 独立显著 SNP DataFrame (行序按 P 升序)
    """
    sig = results[results["SIGNIFICANT"]].copy()
    if sig.empty:
        print("Clumping: 无显著 SNP, 跳过")
        return sig

    # 保留原始行号 (用于索引 dosage)
    sig = sig.sort_values("P")
    orig_idx = sig.index.values

    chroms = sig["CHROM"].apply(_chrom_to_int).values
    positions = sig["POS"].values
    n = len(sig)

    selected = []
    removed = np.zeros(n, dtype=bool)

    for i in range(n):
        if removed[i]:
            continue
        selected.append(i)
        idx_i = orig_idx[i]
        for j in range(i + 1, n):
            if removed[j]:
                continue
            if chroms[j] != chroms[i]:
                continue
            if abs(positions[j] - positions[i]) > window_kb * 1000:
                continue
            idx_j = orig_idx[j]
            if _r2(dosage[idx_i], dosage[idx_j]) > r2_thresh:
                removed[j] = True

    out = sig.iloc[selected].reset_index(drop=True)
    print(f"Clumping: {n} 显著 SNP → {len(out)} 独立信号 "
          f"(r²>{r2_thresh}, 窗口={window_kb}kb)")
    return out