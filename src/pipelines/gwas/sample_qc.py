# src/pipelines/gwas/sample_qc.py
"""样本级 QC: 只做缺失率过滤"""

import numpy as np


def sample_qc(dosage, phenotype, covariates, missing_thresh=0.10):
    """
    输入:
        dosage:      (n_snps, n_samples), 缺失=-1
        phenotype:   DataFrame, index=sample_id
        covariates:  DataFrame 或 None
        missing_thresh: 阈值, None = 跳过
    返回: (dosage, phenotype, covariates, report)
    样本顺序与输入保持一致（只做剔除，不重排）。
    """
    n_samples = dosage.shape[1]

    if missing_thresh is None:
        return dosage, phenotype, covariates, {
            "applied": False,
            "n_samples_before": int(n_samples),
            "n_samples_after": int(n_samples),
            "n_removed": 0,
        }

    # 每列 = 一个样本, axis=0 沿 SNP 求缺失率
    sample_missing = (dosage < 0).mean(axis=0)      # (n_samples,)
    keep = sample_missing <= missing_thresh
    n_kept = int(keep.sum())

    if n_kept == 0:
        raise ValueError("样本 QC 过滤后无样本剩余")

    if n_kept < n_samples:
        idx = np.where(keep)[0]
        dosage = dosage[:, idx]
        phenotype = phenotype.iloc[idx].copy()
        if covariates is not None:
            covariates = covariates.iloc[idx].copy()

    report = {
        "applied": True,
        "n_samples_before": int(n_samples),
        "n_samples_after": n_kept,
        "n_removed": int(n_samples - n_kept),
        "missing_threshold": float(missing_thresh),
    }
    print(f"样本 QC: {n_samples} → {n_kept} 样本 "
          f"(阈值={missing_thresh}, 剔除 {report['n_removed']})")
    return dosage, phenotype, covariates, report