# describe

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/describe.py`](../../../src/task/step/steps/describe.py)
- Tests: [`tests/test_contracts.py`](../../../tests/test_contracts.py), [`tests/test_memory_runtime.py`](../../../tests/test_memory_runtime.py)
- Demo tasks: [`tasks/aggregate_demo/task.yaml`](../../../tasks/aggregate_demo/task.yaml), [`tasks/annotate_demo/task.yaml`](../../../tasks/annotate_demo/task.yaml), [`tasks/annotation_gaps_demo/task.yaml`](../../../tasks/annotation_gaps_demo/task.yaml), [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/barplot_demo/task.yaml`](../../../tasks/barplot_demo/task.yaml), [`tasks/bed_demo/task.yaml`](../../../tasks/bed_demo/task.yaml), [`tasks/bgen_demo/task.yaml`](../../../tasks/bgen_demo/task.yaml), [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/compare_groups_demo/task.yaml`](../../../tasks/compare_groups_demo/task.yaml), [`tasks/concat_demo/task.yaml`](../../../tasks/concat_demo/task.yaml), [`tasks/correction_demo/task.yaml`](../../../tasks/correction_demo/task.yaml), [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/cox_regression_demo/task.yaml`](../../../tasks/cox_regression_demo/task.yaml), [`tasks/csv_demo/task.yaml`](../../../tasks/csv_demo/task.yaml), [`tasks/demo/task.yaml`](../../../tasks/demo/task.yaml), [`tasks/describe_demo/task.yaml`](../../../tasks/describe_demo/task.yaml), [`tasks/distance_matrix_demo/task.yaml`](../../../tasks/distance_matrix_demo/task.yaml), [`tasks/diversity_demo/task.yaml`](../../../tasks/diversity_demo/task.yaml), [`tasks/drop_demo/task.yaml`](../../../tasks/drop_demo/task.yaml), [`tasks/enrich_go_demo/task.yaml`](../../../tasks/enrich_go_demo/task.yaml), [`tasks/enrichment_plot_demo/task.yaml`](../../../tasks/enrichment_plot_demo/task.yaml), [`tasks/explode_demo/task.yaml`](../../../tasks/explode_demo/task.yaml), [`tasks/fasta_demo/task.yaml`](../../../tasks/fasta_demo/task.yaml), [`tasks/filter_by_demo/task.yaml`](../../../tasks/filter_by_demo/task.yaml), [`tasks/filter_min_demo/task.yaml`](../../../tasks/filter_min_demo/task.yaml), [`tasks/find_orfs_demo/task.yaml`](../../../tasks/find_orfs_demo/task.yaml), [`tasks/gc_skew_demo/task.yaml`](../../../tasks/gc_skew_demo/task.yaml), [`tasks/gene_structure_demo/task.yaml`](../../../tasks/gene_structure_demo/task.yaml), [`tasks/gff3_demo/task.yaml`](../../../tasks/gff3_demo/task.yaml), [`tasks/gff_feature_stats_demo/task.yaml`](../../../tasks/gff_feature_stats_demo/task.yaml), [`tasks/go_enrichment_demo/task.yaml`](../../../tasks/go_enrichment_demo/task.yaml), [`tasks/go_enrichment_route_demo/task.yaml`](../../../tasks/go_enrichment_route_demo/task.yaml), [`tasks/gtf_annotation_demo/task.yaml`](../../../tasks/gtf_annotation_demo/task.yaml), [`tasks/gtf_demo/task.yaml`](../../../tasks/gtf_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/h5ad_demo/task.yaml`](../../../tasks/h5ad_demo/task.yaml), [`tasks/hwe_demo/task.yaml`](../../../tasks/hwe_demo/task.yaml), [`tasks/impute_demo/task.yaml`](../../../tasks/impute_demo/task.yaml), [`tasks/interval_analysis_demo/task.yaml`](../../../tasks/interval_analysis_demo/task.yaml), [`tasks/interval_merge_demo/task.yaml`](../../../tasks/interval_merge_demo/task.yaml), [`tasks/interval_overlap_demo/task.yaml`](../../../tasks/interval_overlap_demo/task.yaml), [`tasks/interval_route_demo/task.yaml`](../../../tasks/interval_route_demo/task.yaml), [`tasks/interval_stats_demo/task.yaml`](../../../tasks/interval_stats_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/kaplan_meier_demo/task.yaml`](../../../tasks/kaplan_meier_demo/task.yaml), [`tasks/kmer_count_demo/task.yaml`](../../../tasks/kmer_count_demo/task.yaml), [`tasks/ld_prune_demo/task.yaml`](../../../tasks/ld_prune_demo/task.yaml), [`tasks/log_transform_demo/task.yaml`](../../../tasks/log_transform_demo/task.yaml), [`tasks/logrank_test_demo/task.yaml`](../../../tasks/logrank_test_demo/task.yaml), [`tasks/maf_demo/task.yaml`](../../../tasks/maf_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/missing_demo/task.yaml`](../../../tasks/missing_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/motif_scan_demo/task.yaml`](../../../tasks/motif_scan_demo/task.yaml), [`tasks/mtx_demo/task.yaml`](../../../tasks/mtx_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml), [`tasks/normalize_quantile_demo/task.yaml`](../../../tasks/normalize_quantile_demo/task.yaml), [`tasks/order_axis_demo/task.yaml`](../../../tasks/order_axis_demo/task.yaml), [`tasks/parquet_demo/task.yaml`](../../../tasks/parquet_demo/task.yaml), [`tasks/pca_demo/task.yaml`](../../../tasks/pca_demo/task.yaml), [`tasks/peak_nearest_gene_demo/task.yaml`](../../../tasks/peak_nearest_gene_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml), [`tasks/pivot_demo/task.yaml`](../../../tasks/pivot_demo/task.yaml), [`tasks/plink2_demo/task.yaml`](../../../tasks/plink2_demo/task.yaml), [`tasks/plink_demo/task.yaml`](../../../tasks/plink_demo/task.yaml), [`tasks/prioritize_demo/task.yaml`](../../../tasks/prioritize_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/qc_metrics_demo/task.yaml`](../../../tasks/qc_metrics_demo/task.yaml), [`tasks/rank_axis_demo/task.yaml`](../../../tasks/rank_axis_demo/task.yaml), [`tasks/reduce_axis_demo/task.yaml`](../../../tasks/reduce_axis_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml), [`tasks/regress_demo/task.yaml`](../../../tasks/regress_demo/task.yaml), [`tasks/rename_dim_demo/task.yaml`](../../../tasks/rename_dim_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scale_features_demo/task.yaml`](../../../tasks/scale_features_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/select_demo/task.yaml`](../../../tasks/select_demo/task.yaml), [`tasks/sequence_features_route_demo/task.yaml`](../../../tasks/sequence_features_route_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml), [`tasks/sequence_stats_demo/task.yaml`](../../../tasks/sequence_stats_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/sop_demo/task.yaml`](../../../tasks/sop_demo/task.yaml), [`tasks/survival_demo/task.yaml`](../../../tasks/survival_demo/task.yaml), [`tasks/transpose_demo/task.yaml`](../../../tasks/transpose_demo/task.yaml), [`tasks/vcf_demo/task.yaml`](../../../tasks/vcf_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

This operator has no parameters.

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "report"
}
```

## Processing rules (source docstring)

```text
Print a summary of one input form.

    Params: none.

--- module documentation ---

Describe step: print and export a summary of an input form.
```

## Minimal YAML skeleton

```yaml
- name: describe
  inputs: [<input1>]
  params:
    {}
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（数据概览）

- 不修改数据，只输出 shape、dims、info、有限值统计和缺失数量；适合作为中间检查点。
- 统计为有限值统计：NaN/Inf 不计入 min/max/mean/std，但 `n_missing` 会报告数量。
- 大矩阵走 `flat-reduction-v1` 流式路径，float64 矩可能与一次性 NumPy 有极小舍入差。
- 不替代 QC：不检查标签重复、编码一致性、批次或分布假设。
- 均值/标准差是全局的，不是按样本/基因分层；分层统计用 `qc_metrics` 或 `reduce_axis`。
