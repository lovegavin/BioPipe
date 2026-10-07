# src/pipelines/gwas/profile.py
"""数据特征快照"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np


def build_dataset_profile(geno_rel, pheno_rel, covar_rel,
                          dosage, variant_info, sample_ids, ploidy,
                          phenotype, covariates):
    valid = dosage[dosage >= 0]

    dosage_valid = np.where(dosage < 0, np.nan, dosage)
    alt_freq = np.nanmean(dosage_valid, axis=1) / ploidy
    maf = np.minimum(alt_freq, 1 - alt_freq)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pipeline": "gwas",
        "input": {
            "genotype":   geno_rel,
            "phenotype":  pheno_rel,
            "covariates": covar_rel,
        },
        "genotype": {
            "n_samples": int(dosage.shape[1]),
            "n_snps": int(dosage.shape[0]),
            "ploidy": int(ploidy),
            "chromosomes": sorted(variant_info["CHROM"].unique().tolist()),
            "dosage_range": (
                [int(valid.min()), int(valid.max())] if valid.size else [0, 0]
            ),
            "missing_rate_overall": float((dosage < 0).mean()),
            "maf_quantiles": {
                "min": float(np.nanmin(maf)),
                "q25": float(np.nanpercentile(maf, 25)),
                "median": float(np.nanmedian(maf)),
                "q75": float(np.nanpercentile(maf, 75)),
                "max": float(np.nanmax(maf)),
            },
        },
        "phenotype": _profile_phenotype(phenotype),
        "covariates": _profile_covariates(covariates),
    }


def _profile_phenotype(phenotype):
    y = phenotype["trait_value"].values.astype(float)
    n_unique = int(len(np.unique(y)))
    return {
        "n_samples": int(len(y)),
        "trait_name": phenotype.columns[0],
        "type": "binary" if n_unique == 2 else "continuous",
        "n_unique": n_unique,
        "mean": float(np.mean(y)),
        "std": float(np.std(y)),
        "min": float(np.min(y)),
        "max": float(np.max(y)),
        "n_missing": int(np.isnan(y).sum()),
    }


def _profile_covariates(covariates):
    if covariates is None:
        return None
    return {
        "n_samples": int(covariates.shape[0]),
        "columns": list(covariates.columns),
        "n_columns": int(covariates.shape[1]),
        "n_missing_total": int(covariates.isna().sum().sum()),
    }


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)