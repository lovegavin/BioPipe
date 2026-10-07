# src/pipelines/gwas/association.py
"""逐 SNP 回归: 连续 → OLS, 二分类 → Firth (或 Logit)"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.pipelines.gwas.firth import fit_firth


def phenotype_type(y):
    return "binary" if len(np.unique(y)) == 2 else "continuous"


def regress(dosage, variant_info, maf, phenotype, covariates,
            binary_model="firth"):
    """
    返回: DataFrame [CHROM, POS, ID, REF, ALT, BETA, SE, P, MAF, N]
    """
    y = phenotype["trait_value"].values.astype(float)
    n_snps, n_samples = dosage.shape
    ptype = phenotype_type(y)
    print(f"表型类型: {ptype}")
    if ptype == "binary":
        print(f"  二分类模型: {binary_model}")

    if covariates is not None and covariates.shape[1] > 0:
        cov = covariates.values.astype(float)
        if np.isnan(cov).any():
            raise ValueError("协变量含缺失值, 请先清洗")
    else:
        cov = None

    rows = []
    for i in range(n_snps):
        g = dosage[i]
        valid = g >= 0
        n_valid = int(valid.sum())

        if n_valid < 3:
            rows.append((np.nan, np.nan, np.nan, n_valid))
            continue

        X = g[valid][:, None]
        if cov is not None:
            X = np.hstack([X, cov[valid]])
        X = sm.add_constant(X, has_constant="add")
        y_sub = y[valid]

        if ptype == "binary" and len(np.unique(y_sub)) < 2:
            rows.append((np.nan, np.nan, np.nan, n_valid))
            continue

        beta = se = pval = np.nan
        if ptype == "continuous":
            model = sm.OLS(y_sub, X).fit()
            beta = float(model.params[1])
            se = float(model.bse[1])
            pval = float(model.pvalues[1])
        elif binary_model == "firth":
            res = fit_firth(y_sub, X)
            if res is not None:
                b_arr, se_arr, p_arr = res
                beta = float(b_arr[1])
                se = float(se_arr[1])
                pval = float(p_arr[1])
        else:  # logit
            model = sm.Logit(y_sub, X).fit(disp=0, maxiter=200)
            beta = float(model.params[1])
            se = float(model.bse[1])
            pval = float(model.pvalues[1])

        rows.append((beta, se, pval, n_valid))

    res = pd.DataFrame(rows, columns=["BETA", "SE", "P", "N"])
    out = pd.concat([variant_info.reset_index(drop=True), res], axis=1)
    out["MAF"] = maf

    n_ok = int(out["P"].notna().sum())
    print(f"完成: {n_ok} / {n_snps} SNP")

    return out[["CHROM", "POS", "ID", "REF", "ALT",
                "BETA", "SE", "P", "MAF", "N"]]