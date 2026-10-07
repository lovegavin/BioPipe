# src/pipelines/gwas/config.py
"""GWAS 默认配置与校验"""


def default_config():
    return {
        "pipeline": "gwas",
        "input": {
            "genotype": None,        # VCF 或 PLINK (.bed)
            "phenotype": None,
            "covariates": None,
        },
        "qc": {
            "maf": 0.01,
            "missing": 0.10,
            "sample_missing": 0.10,
            "hwe": 1e-6,
        },
        "ld": {
            "prune": True,
            "r2": 0.2,
            "window": 100,
            "clump": True,
            "clump_r2": 0.5,
            "clump_window": 500,
        },
        "pca": {
            "enabled": True,
            "n_components": 10,
            "as_covariates": True,
        },
        "association": {
            "binary_model": "firth",
        },
        "correction": {
            "method": "bonferroni",
            "fdr_threshold": 0.05,
        },
        "plots": {
            "manhattan": True,
            "qq": True,
            "volcano": True,
            "forest": True,
            "maf_distribution": True,
            "pvalue_histogram": True,
            "chromosome_density": True,
            "effect_vs_maf": True,
            "pca_scatter": True,
            "pca_scree": True,
            "top_n_forest": 20,
        },
    }


def validate_config(config):
    if config.get("pipeline") != "gwas":
        raise ValueError(
            f"pipeline 必须为 'gwas', 实际: {config.get('pipeline')}"
        )
    input_cfg = config.get("input", {})
    for key in ("genotype", "phenotype"):
        if not input_cfg.get(key):
            raise ValueError(f"config.input.{key} 必填")