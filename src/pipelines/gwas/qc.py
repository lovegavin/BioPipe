# src/pipelines/gwas/qc.py
"""SNP QC: 缺失率 + MAF + HWE (二倍体)"""

import numpy as np


# ---------- Wigginton 2005 HWE 精确检验 ----------
def _hwe_exact(obs_hom1, obs_hets, obs_hom2):
    """
    Wigginton et al. 2005 精确检验。
    输入为三种基因型计数 (纯合 ref, 杂合, 纯合 alt)。
    返回 HWE p 值。
    """
    if obs_hets > obs_hom1 + obs_hom2:
        obs_hom1, obs_hom2 = obs_hom2, obs_hom1

    obs_homc = min(obs_hom1, obs_hom2)
    obs_homr = max(obs_hom1, obs_hom2)
    rare = 2 * obs_homc + obs_hets
    genotypes = obs_hets + obs_homr + obs_homc

    if genotypes == 0:
        return 1.0

    probs = np.zeros(rare + 1, dtype=float)
    mid = rare * (2 * genotypes - rare) // (2 * genotypes)
    if mid % 2 != rare % 2:
        mid += 1
    probs[mid] = 1.0

    curr_hets = mid
    curr_homr = (rare - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets > 1:
        probs[curr_hets - 2] = (
            probs[curr_hets] * curr_hets * (curr_hets - 1)
            / (4.0 * (curr_homr + 1) * (curr_homc + 1))
        )
        curr_homr += 1
        curr_homc += 1
        curr_hets -= 2

    curr_hets = mid
    curr_homr = (rare - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets <= rare - 2:
        probs[curr_hets + 2] = (
            probs[curr_hets] * 4.0 * curr_homr * curr_homc
            / ((curr_hets + 2) * (curr_hets + 1))
        )
        curr_homr -= 1
        curr_homc -= 1
        curr_hets += 2

    total = probs.sum()
    if total <= 0:
        return 1.0
    probs /= total
    p = probs[probs <= probs[obs_hets]].sum()
    return float(min(max(p, 0.0), 1.0))


def _is_binary(phenotype):
    if phenotype is None:
        return False
    y = phenotype["trait_value"].values
    return len(np.unique(y)) == 2


def _compute_hwe_pvals(dosage, phenotype):
    """逐 SNP 计算 HWE p 值。二分类时只在对照组 (y==0) 计算。"""
    n_snps, n_samples = dosage.shape
    pvals = np.full(n_snps, np.nan, dtype=float)

    if _is_binary(phenotype):
        y = phenotype["trait_value"].values
        ctrl_mask = (y == 0)
        if ctrl_mask.sum() < 10:
            print("警告: 对照组样本 < 10, 回退到全样本做 HWE")
            ctrl_mask = np.ones(n_samples, dtype=bool)
        scope = "controls_only" if ctrl_mask.sum() < n_samples else "all_samples"
    else:
        ctrl_mask = np.ones(n_samples, dtype=bool)
        scope = "all_samples"

    for j in range(n_snps):
        col = dosage[j][ctrl_mask]
        valid = col[col >= 0]
        if valid.size < 3:
            continue
        n_aa = int(np.sum(valid == 0))
        n_ab = int(np.sum(valid == 1))
        n_bb = int(np.sum(valid == 2))
        pvals[j] = _hwe_exact(n_aa, n_ab, n_bb)

    return pvals, scope


# ---------- 主入口 ----------
def qc(dosage, variant_info, ploidy, phenotype=None,
       maf_thresh=0.01, missing_thresh=0.10, hwe_thresh=1e-6):
    """
    返回: (dosage_filt, variant_info_filt, maf, report)
    HWE 规则:
        ploidy == 2 且 hwe_thresh 非 None → 做 HWE 过滤
        ploidy > 2                       → 跳过
        hwe_thresh is None               → 跳过
    """
    n_snps = dosage.shape[0]

    # 1. 缺失率
    missing = (dosage < 0).mean(axis=1)             # (n_snps,)

    # 2. MAF
    dosage_valid = np.where(dosage < 0, np.nan, dosage)
    alt_freq = np.nanmean(dosage_valid, axis=1) / ploidy
    maf = np.minimum(alt_freq, 1 - alt_freq)

    keep = (missing <= missing_thresh) & (maf >= maf_thresh)
    n_removed_missing = int((missing > missing_thresh).sum())
    n_removed_maf = int(
        ((missing <= missing_thresh) & (maf < maf_thresh)).sum()
    )

    # 3. HWE
    hwe_info = {"applied": False}
    if ploidy == 2 and hwe_thresh is not None:
        hwe_pvals, scope = _compute_hwe_pvals(dosage, phenotype)
        with np.errstate(invalid="ignore"):
            hwe_fail = (~np.isnan(hwe_pvals)) & (hwe_pvals < hwe_thresh)
        n_removed_hwe = int((keep & hwe_fail).sum())
        keep &= ~hwe_fail
        hwe_info = {
            "applied": True,
            "threshold": float(hwe_thresh),
            "scope": scope,
            "n_removed": n_removed_hwe,
        }
    elif ploidy > 2:
        hwe_info = {
            "applied": False,
            "skipped_reason": "polyploid",
            "recommendation": "Use 'hwep' R package for polyploid HWE",
        }
    else:
        hwe_info = {"applied": False, "skipped_reason": "disabled"}

    report = {
        "ploidy": int(ploidy),
        "maf_threshold": float(maf_thresh),
        "missing_threshold": float(missing_thresh),
        "n_snps_before": int(n_snps),
        "n_snps_after": int(keep.sum()),
        "n_removed_missing": n_removed_missing,
        "n_removed_maf": n_removed_maf,
        "hwe": hwe_info,
    }

    print(f"SNP QC: {n_snps} → {int(keep.sum())} SNP "
          f"(缺失剔除 {n_removed_missing}, MAF 剔除 {n_removed_maf})")
    if hwe_info.get("applied"):
        print(f"  HWE: 移除 {hwe_info['n_removed']} SNP "
              f"(scope={hwe_info['scope']})")
    elif hwe_info.get("skipped_reason"):
        print(f"  HWE: 跳过 ({hwe_info['skipped_reason']})")

    return (
        dosage[keep],
        variant_info.iloc[keep].reset_index(drop=True),
        maf[keep],
        report,
    )