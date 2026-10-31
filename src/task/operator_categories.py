"""Canonical operator categories shared by the registry and Studio.

The bundled library deliberately uses a small, stable vocabulary.  A category
is a navigation aid, not a biological claim: operators that do not obviously
belong elsewhere live under Statistics.  Plugin authors may still use custom
labels; only the bundled manifest is checked against this list.
"""

from __future__ import annotations

CANONICAL_CATEGORIES = (
    "Data",
    "Statistics",
    "Machine Learning",
    "Omics",
    "Visualization",
    "Quality Control",
)

# Categories that already mean a canonical value, plus legacy spellings.
_ALIASES = {
    "data": "Data",
    "data preparation": "Data",
    "数据整理": "Data",
    "statistics": "Statistics",
    "statistical analysis": "Statistics",
    "统计分析": "Statistics",
    "survival": "Statistics",
    "analysis": "Statistics",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "omics": "Omics",
    "genetics": "Omics",
    "genomics": "Omics",
    "transcriptomics": "Omics",
    "expression": "Omics",
    "single cell": "Omics",
    "single-cell": "Omics",
    "microbiome": "Omics",
    "metagenomics": "Omics",
    "sequence": "Omics",
    "proteomics": "Omics",
    "visualization": "Visualization",
    "visualisation": "Visualization",
    "可视化": "Visualization",
    "quality control": "Quality Control",
    "quality_control": "Quality Control",
    "质量控制": "Quality Control",
}

# Analysis-category operators whose primary job is table preparation rather
# than inference.
_DATA_OVERRIDES = {
    "bin",
    "cluster_axis",
    "combat",
    "filter_by",
    "min_max_scale",
    "power_transform",
    "pseudobulk",
    "quantile_transform",
    "rank_axis",
    "rank_transform",
    "reduce_axis",
    "remove_batch_effect",
    "robust_scale",
    "softmax",
    "winsorize",
    "zscore",
}

_QC_OVERRIDES = {"doublet_detect", "flow_compensate", "flow_gate"}

_OMICS_OVERRIDES = {
    "annotation_gaps",
    "enrich_go",
    "find_orfs",
    "gc_skew_profile",
    "gene_list_to_hits",
    "gene_structure",
    "gff_feature_stats",
    "gsea",
    "interval_merge",
    "interval_overlap",
    "interval_stats",
    "kmer_count",
    "limma_de",
    "motif_scan",
    "ora",
    "peak_nearest_gene",
    "sequence_stats",
    "ssgsea",
}

# Meta-analysis is a statistical method even when the source registry once
# grouped it with genetics.
_META_OVERRIDES = {"egger_test", "leave_one_out", "meta_analysis", "meta_regression"}

# Unsupervised learning, dimensionality reduction and clustering validation.
_ML_UNSUPERVISED = {
    "adjusted_mutual_info",
    "adjusted_rand",
    "adjusted_rand_index",
    "agglomerative",
    "calinski_harabasz",
    "davies_bouldin",
    "dbscan",
    "dunn_index",
    "factor_analysis",
    "fowlkes_mallows",
    "gaussian_mixture",
    "gaussian_random_projection",
    "homogeneity_completeness_v_measure",
    "ica",
    "isolation_forest",
    "isomap",
    "kernel_pca",
    "locally_linear_embedding",
    "mds",
    "mutual_information",
    "nmf",
    "normalized_mutual_info",
    "pair_confusion_matrix",
    "pca_loadings",
    "silhouette",
    "silhouette_samples",
    "silhouette_score",
    "spectral_embedding",
    "topic_lda",
    "truncated_svd",
    "tsne",
    "umap",
    "variation_of_information",
}

# Regression models whose names do not end in ``_regressor``.
_ML_REGRESSIONS = {
    "lasso_regression",
    "linear_regression",
    "logistic_regression",
    "pls_regression",
    "quantile_regression",
    "ridge_regression",
}


def _is_ml(name: str) -> bool:
    return (
        name in _ML_UNSUPERVISED
        or name in _ML_REGRESSIONS
        or name.endswith(("_classifier", "_regressor"))
    )


def category_for_operator(name: str, raw: str | None) -> str:
    """Return the canonical category for one bundled operator."""
    if name in _DATA_OVERRIDES:
        return "Data"
    if name in _QC_OVERRIDES:
        return "Quality Control"
    if name in _META_OVERRIDES:
        return "Statistics"
    if name in _OMICS_OVERRIDES:
        return "Omics"

    key = (raw or "").strip()
    folded = key.casefold()
    if folded in ("analysis", "statistics", "统计分析", "survival"):
        return "Machine Learning" if _is_ml(name) else "Statistics"
    if folded.startswith("data"):
        return "Data"
    return _ALIASES.get(folded, "Other")
