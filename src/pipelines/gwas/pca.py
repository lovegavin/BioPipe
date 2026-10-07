# src/pipelines/gwas/pca.py
"""PCA 群体结构校正"""

import numpy as np
import pandas as pd


def compute_pca(dosage, n_components=10):
    """
    返回: pcs (n_samples, n_components), explained_var_ratio (n_components,)
    """
    X = dosage.T.astype(np.float64)

    mask = X < 0
    if mask.any():
        col_mean = np.nanmean(np.where(mask, np.nan, X), axis=0)
        col_mean = np.nan_to_num(col_mean, nan=0.0)
        idx = np.where(mask)
        X[idx] = np.take(col_mean, idx[1])

    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    std[std < 1e-8] = 1.0
    X = (X - mean) / std

    U, S, _ = np.linalg.svd(X, full_matrices=False)
    n_comp = min(n_components, S.size)
    pcs = U[:, :n_comp] * S[:n_comp]
    var = S ** 2
    explained_var_ratio = var[:n_comp] / var.sum()

    print(f"PCA: {n_comp} PCs, "
          f"PC1={explained_var_ratio[0]*100:.2f}%, "
          f"PC2={explained_var_ratio[1]*100:.2f}%")

    return pcs, explained_var_ratio


def append_pcs(covariates, pcs):
    """把 PCs 拼接到协变量 DataFrame（列拼接，行顺序保持一致）"""
    pc_df = pd.DataFrame(
        pcs,
        columns=[f"PC{i+1}" for i in range(pcs.shape[1])],
    )
    if covariates is None:
        return pc_df
    return pd.concat(
        [covariates.reset_index(drop=True),
         pc_df.reset_index(drop=True)],
        axis=1,
    )