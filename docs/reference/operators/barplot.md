# barplot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/barplot.py`](../../../src/task/step/steps/barplot.py)
- Tests: [`tasks/barplot_demo/test_barplot.py`](../../../tasks/barplot_demo/test_barplot.py)
- Demo tasks: [`tasks/barplot_demo/task.yaml`](../../../tasks/barplot_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `sample_dim` | 分析维度 | string |  |  |  | yes | basic |
| `filename` | 分析维度 | string |  |  |  | yes | basic |
| `top_n` | 保留数量 | integer / null | 20 | 0 |  |  | basic |
| `other_label` | 另一维度标签 | string | Other |  |  |  | basic |
| `normalize` | 归一化 | boolean | True |  |  |  | basic |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string |  |  |  |  | basic |
| `ylabel` | Y 轴标题 | string |  |  |  |  | basic |
| `cmap` | 配色 | string | tab20 |  |  |  | advanced |
| `figsize` | 图片尺寸 | array |  |  |  |  | advanced |
| `legend` | 显示图例 | boolean | True |  |  |  | advanced |
| `legend_ncol` | 图例列数 | integer | 3 | 1 |  |  | advanced |
| `rotate_labels` | 旋转标签 | boolean | True |  |  |  | advanced |

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
      },
      {
        "param": "sample_dim",
        "default": null
      }
    ],
    "labels": [],
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
Stacked bar plot of a matrix along one axis.

--- module documentation ---

Stacked bar plot of a matrix along one axis.

Input is a 2D form. One axis is the "composition" axis (features
that will be stacked) and the other is the "sample" axis (bars).
For each sample, one bar is drawn, and the features are stacked in
their order along the composition axis.

This is the standard visualization for compositional data:
relative abundance of taxa per sample, cell-type fractions per
sample, isoform fractions, etc.

Layout
------
    input  dims: [<composition_dim>, <sample_dim>]  (any orientation)
    output      : a barplot image

Feature selection
-----------------
The operator can show only the top N most abundant features. The
remaining features are summed into a single "Other" category.

Normalization
-------------
``normalize=True`` (default) divides each sample by its total, so
each bar sums to 1. This is the correct default for compositional
data. Set to False to plot raw values.

Params:
    dim          : composition dim (required)
    sample_dim   : sample dim (required)
    top_n        : show only the top N most abundant features
                   (default 20; use 0 or None to show all)
    other_label  : label for the aggregated remainder
                   (default "Other")
    normalize    : divide each sample by its total (default True)
    filename     : output file name (required)
    title        : optional plot title
    xlabel       : optional x label (default: sample_dim)
    ylabel       : optional y label (default: "Fraction" or "Value")
    cmap         : matplotlib colormap (default "tab20")
    figsize      : [width, height] in inches (default auto)
    legend       : show a legend (default True)
    legend_ncol  : number of columns in the legend (default 3)
    rotate_labels: rotate x tick labels 90 degrees (default True)
```

## Minimal YAML skeleton

```yaml
- name: barplot
  inputs: [<input1>]
  params:
    dim: <string>
    sample_dim: <string>
    filename: <string>
    top_n: <integer / null>
    other_label: <string>
    normalize: <boolean>
    title: <string>
    xlabel: <string>
    ylabel: <string>
    cmap: <string>
    figsize: <array>
    legend: <boolean>
    legend_ncol: <integer>
    rotate_labels: <boolean>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/barplot.md` and regenerate.
