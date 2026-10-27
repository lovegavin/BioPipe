# dotplot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/dotplot.py`](../../../src/task/step/steps/dotplot.py)
- Tests: [`tasks/dotplot_demo/test_dotplot.py`](../../../tasks/dotplot_demo/test_dotplot.py)
- Demo tasks: [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml)
- Inputs arity: `2`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string |  |  |  | yes | basic |
| `group_dim` | 特征维度 | string |  |  |  | yes | basic |
| `features` | 特征列表 | array |  |  |  | yes | basic |
| `group_label` | 特征维度 | string |  |  |  | yes | basic |
| `groups` | 分组顺序 | array |  |  |  |  | basic |
| `statistic` | 统计量 | string; enum=['mean', 'median', 'sum'] | mean |  |  |  | basic |
| `proportion_mode` | 比例模式 | string; enum=['nonzero', 'threshold'] | nonzero |  |  |  | basic |
| `threshold` | 阈值 | number | 0 |  |  |  | basic |
| `filename` | 特征维度 | string |  |  |  | yes | basic |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string |  |  |  |  | basic |
| `ylabel` | Y 轴标题 | string |  |  |  |  | basic |
| `cmap` | 配色 | string | viridis |  |  |  | advanced |
| `dot_scale` | 点大小 | number | 200 |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "feature_dim",
        "default": null
      },
      {
        "param": "group_dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  },
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "group_dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "group_label",
        "default": null
      }
    ]
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
Dot plot of features grouped by a label column.

--- module documentation ---

Dot plot of feature values grouped by a label column.

Two inputs share a sample dim. The first carries per-feature values
across samples; the second carries group labels. For each (group,
feature) cell the operator computes two statistics:

    value       mean (or median, or sum) of the feature within
                the group
    proportion  fraction of samples in the group whose value passes
                the "expressed" rule (non-zero by default)

The result is drawn as a grid: x = features, y = groups, dot color
= value, dot size = proportion. This is the standard marker dot
plot in single-cell analysis, but it works on any two-form dataset
with a grouping column.

The same two statistics are exported as a table so the numbers are
auditable.

Params:
    feature_dim     : feature dim on the data form (required)
    group_dim       : sample dim shared by both forms (required)
    features        : list of feature labels to show (required)
    group_label     : column on the metadata's other dim (required)
    groups          : optional list of groups to show, in order
    statistic       : "mean" | "median" | "sum" (default "mean")
    proportion_mode : "nonzero" | "threshold" (default "nonzero")
    threshold       : value used when proportion_mode="threshold"
    filename        : output file name (required)
    title           : optional plot title
    xlabel          : optional x label (default: feature_dim)
    ylabel          : optional y label (default: group_label)
    cmap            : matplotlib colormap (default "viridis")
    dot_scale       : max dot size in points^2 (default 200)
```

## Minimal YAML skeleton

```yaml
- name: dotplot
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    group_dim: <string>
    features: <array>
    group_label: <string>
    groups: <array>
    statistic: <string; enum=['mean', 'median', 'sum']>
    proportion_mode: <string; enum=['nonzero', 'threshold']>
    threshold: <number>
    filename: <string>
    title: <string>
    xlabel: <string>
    ylabel: <string>
    cmap: <string>
    dot_scale: <number>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/dotplot.md` and regenerate.
