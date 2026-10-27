# histogram

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/histogram.py`](../../../src/task/step/steps/histogram.py)
- Tests: none found
- Demo tasks: [`tasks/annotation_gaps_demo/task.yaml`](../../../tasks/annotation_gaps_demo/task.yaml), [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/find_orfs_demo/task.yaml`](../../../tasks/find_orfs_demo/task.yaml), [`tasks/gene_structure_demo/task.yaml`](../../../tasks/gene_structure_demo/task.yaml), [`tasks/gtf_annotation_demo/task.yaml`](../../../tasks/gtf_annotation_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/interval_analysis_demo/task.yaml`](../../../tasks/interval_analysis_demo/task.yaml), [`tasks/interval_merge_demo/task.yaml`](../../../tasks/interval_merge_demo/task.yaml), [`tasks/interval_overlap_demo/task.yaml`](../../../tasks/interval_overlap_demo/task.yaml), [`tasks/interval_stats_demo/task.yaml`](../../../tasks/interval_stats_demo/task.yaml), [`tasks/peak_nearest_gene_demo/task.yaml`](../../../tasks/peak_nearest_gene_demo/task.yaml), [`tasks/qc_metrics_demo/task.yaml`](../../../tasks/qc_metrics_demo/task.yaml), [`tasks/sequence_features_route_demo/task.yaml`](../../../tasks/sequence_features_route_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml), [`tasks/sequence_stats_demo/task.yaml`](../../../tasks/sequence_stats_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `bins` | 分箱数量 | integer | 40 | 1 |  |  | basic |
| `dim` | 数值维度 | string | feature |  |  |  | basic |
| `filename` | 文件名 | string |  |  |  | yes | basic |
| `log_y` | Log Y axis | boolean | False |  |  |  | basic |
| `title` | Title | string |  |  |  |  | basic |
| `value_label` | 数值标签 | string |  |  |  | yes | basic |
| `xlabel` | X axis label | string |  |  |  |  | basic |
| `ylabel` | Y axis label | string | Count |  |  |  | basic |

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
        "default": "feature"
      }
    ],
    "labels": [
      {
        "dim": {
          "param": "dim",
          "default": "feature"
        },
        "values": {
          "param": "value_label",
          "default": null
        }
      }
    ],
    "parallel": [],
    "ndim": 2
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
Draw a histogram.

Params:
    dim         : attribute dimension (default "feature")
    value_label : column label for the values
    bins        : number of bins (default 40)
    filename    : output file name
    title       : optional plot title
    xlabel      : optional x-axis label (default: value_label)
    ylabel      : optional y-axis label (default: "Count")
    log_y       : use log scale on the y axis (default False)

--- module documentation ---

Histogram operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations.

The operator reads one labeled column and plots its distribution.
```

## Minimal YAML skeleton

```yaml
- name: histogram
  inputs: [<input1>]
  params:
    bins: <integer>
    dim: <string>
    filename: <string>
    log_y: <boolean>
    title: <string>
    value_label: <string>
    xlabel: <string>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/histogram.md` and regenerate.
