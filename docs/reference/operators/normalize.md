# normalize

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/normalize.py`](../../../src/task/step/steps/normalize.py)
- Tests: [`tasks/ml_classification_route_demo/test_ml_classification.py`](../../../tasks/ml_classification_route_demo/test_ml_classification.py), [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py), [`tasks/multi_omics_route_demo/test_multi_omics_route.py`](../../../tasks/multi_omics_route_demo/test_multi_omics_route.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_ml_classification.py`](../../../tasks/verify_ml_classification.py), [`tasks/verify_ml_regression.py`](../../../tasks/verify_ml_regression.py), [`tasks/verify_multi_omics.py`](../../../tasks/verify_multi_omics.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py), [`tests/test_extension12.py`](../../../tests/test_extension12.py), [`tests/test_r_oracles4.py`](../../../tests/test_r_oracles4.py)
- Demo tasks: [`tasks/aggregate_demo/task.yaml`](../../../tasks/aggregate_demo/task.yaml), [`tasks/barplot_demo/task.yaml`](../../../tasks/barplot_demo/task.yaml), [`tasks/boxplot_demo/task.yaml`](../../../tasks/boxplot_demo/task.yaml), [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/distance_matrix_demo/task.yaml`](../../../tasks/distance_matrix_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/heatmap_demo/task.yaml`](../../../tasks/heatmap_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/log_transform_demo/task.yaml`](../../../tasks/log_transform_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml), [`tasks/normalize_demo/task.yaml`](../../../tasks/normalize_demo/task.yaml), [`tasks/normalize_quantile_demo/task.yaml`](../../../tasks/normalize_quantile_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/rank_axis_demo/task.yaml`](../../../tasks/rank_axis_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scale_features_demo/task.yaml`](../../../tasks/scale_features_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `method` | 方法 | any; enum=['cpm', 'total', 'median_of_ratios', 'quantile', 'zscore'] |  |  |  | yes | basic |
| `target_sum` | 目标总量 | number | 1000000.0 | 0 |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "transform",
  "representation": "normalize"
}
```

## Processing rules (source docstring)

```text
Normalize a Form along one dimension.

--- module documentation ---

Normalize a Form along one dimension.

Applies a sample-level normalization. Standard second step after
filtering, for any count or intensity matrix (RNA-seq, proteomics,
metabolomics, single-cell).

Supported methods
-----------------
    cpm                counts per million: divide each sample by its
                       total, then scale to ``target_sum``
    total              divide each sample by its total (sum = 1)
    median_of_ratios   DESeq2 size factors: per-gene geometric mean,
                       per-sample median of ratios
    quantile           quantile normalization: for each rank position,
                       replace the value with the mean of that rank
                       across all samples
    zscore             z-score each sample (mean 0, std 1)

Layout
------
Input is any Form. The normalization runs along ``dim`` (typically
the sample axis); every other axis is flattened.

Output has the same dims, labels, info and axis_info as the input.
Only ``data`` is replaced.

Params:
    method     : "cpm" | "total" | "median_of_ratios" | "quantile"
                 | "zscore"
    dim        : sample dimension
    target_sum : target total for ``cpm`` (default 1e6)
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: normalize
  inputs: [<input1>]
  params:
    dim: <string>
    method: <any; enum=['cpm', 'total', 'median_of_ratios', 'quantile', 'zscore']>
    target_sum: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/normalize.md` and regenerate.
