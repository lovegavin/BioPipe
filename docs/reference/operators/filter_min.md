# filter_min

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/filter_min.py`](../../../src/task/step/steps/filter_min.py)
- Tests: [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/aggregate_demo/task.yaml`](../../../tasks/aggregate_demo/task.yaml), [`tasks/barplot_demo/task.yaml`](../../../tasks/barplot_demo/task.yaml), [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/boxplot_demo/task.yaml`](../../../tasks/boxplot_demo/task.yaml), [`tasks/compare_groups_demo/task.yaml`](../../../tasks/compare_groups_demo/task.yaml), [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/distance_matrix_demo/task.yaml`](../../../tasks/distance_matrix_demo/task.yaml), [`tasks/diversity_demo/task.yaml`](../../../tasks/diversity_demo/task.yaml), [`tasks/filter_min_demo/task.yaml`](../../../tasks/filter_min_demo/task.yaml), [`tasks/heatmap_demo/task.yaml`](../../../tasks/heatmap_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/log_transform_demo/task.yaml`](../../../tasks/log_transform_demo/task.yaml), [`tasks/ma_plot_demo/task.yaml`](../../../tasks/ma_plot_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/normalize_demo/task.yaml`](../../../tasks/normalize_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/volcano_demo/task.yaml`](../../../tasks/volcano_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `min_samples` | 最少样本数 | integer | 1 | 1 |  |  | basic |
| `min_value` | 最低信号 | integer | 1 | 0 |  |  | basic |

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
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Drop positions that do not reach a minimum value.

--- module documentation ---

Filter positions along one dimension by a minimum value.

Keeps positions whose value reaches ``min_value`` in at least
``min_samples`` samples. Domain-agnostic: works on any 2D form.

    pass[i, j] = valid[i, j] and data[i, j] >= min_value
    keep[i]    = sum_j(pass[i, j]) >= min_samples

Missing values never count as a passing sample.

Params:
    dim         : dimension to filter along
    min_value   : per-sample threshold (default 1)
    min_samples : minimum number of samples that must pass
                  (default 1)
    output      : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: filter_min
  inputs: [<input1>]
  params:
    dim: <string>
    min_samples: <integer>
    min_value: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/filter_min.md` and regenerate.
