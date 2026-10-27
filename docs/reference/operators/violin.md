# violin

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/violin.py`](../../../src/task/step/steps/violin.py)
- Tests: [`tasks/violin_demo/test_violin.py`](../../../tasks/violin_demo/test_violin.py)
- Demo tasks: [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `2`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `group_dim` | 数值字段 | string |  |  |  | yes | basic |
| `group_label` | 数值字段 | string |  |  |  | yes | basic |
| `groups` | 分组顺序 | array |  |  |  |  | basic |
| `filename` | 数值字段 | string |  |  |  | yes | basic |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string |  |  |  |  | basic |
| `ylabel` | Y 轴标题 | string |  |  |  |  | basic |
| `inner` | 内部显示 | string; enum=['box', 'quartile', 'point', 'none'] | box |  |  |  | basic |
| `show_points` | 显示散点 | boolean | False |  |  |  | advanced |
| `point_size` | 点大小 | number | 4 |  |  |  | advanced |
| `point_alpha` | 点透明度 | number | 0.5 | 0 | 1 |  | advanced |
| `rotate_labels` | 旋转标签 | boolean | False |  |  |  | advanced |

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
      },
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
        "param": "value_label",
        "default": null
      }
    ]
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
Draw violin plots of a value column grouped by a label.

--- module documentation ---

Violin plot of one value column split by groups.

Two inputs share a sample dim. The first carries a per-sample value
column; the second carries a group label column. For each group the
operator draws a kernel density estimate of the values, optionally
with an inner box, quartile markers, or points.

Domain-agnostic. Any 2D data form + any 2D metadata form with a
grouping column works.

Params:
    dim             : dim of the data form that holds the value
                      column (default "feature")
    value_label     : column label to plot (required)
    group_dim       : sample dim shared by both forms (required)
    group_label     : column label on the metadata's other dim
                      (required)
    groups          : optional list of group names to keep, in order
    filename        : output file name (required)
    title           : optional plot title
    xlabel          : optional x label (default: group_label)
    ylabel          : optional y label (default: value_label)
    inner           : "box" | "quartile" | "point" | "none"
                      (default "box")
    show_points     : overlay individual points (default False)
    point_size      : marker size for overlay (default 4)
    point_alpha     : marker transparency (default 0.5)
    rotate_labels   : rotate x tick labels 45 degrees (default False)
```

## Minimal YAML skeleton

```yaml
- name: violin
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    value_label: <string>
    group_dim: <string>
    group_label: <string>
    groups: <array>
    filename: <string>
    title: <string>
    xlabel: <string>
    ylabel: <string>
    inner: <string; enum=['box', 'quartile', 'point', 'none']>
    show_points: <boolean>
    point_size: <number>
    point_alpha: <number>
    rotate_labels: <boolean>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/violin.md` and regenerate.
