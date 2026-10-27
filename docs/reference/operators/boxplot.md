# boxplot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/boxplot.py`](../../../src/task/step/steps/boxplot.py)
- Tests: none found
- Demo tasks: [`tasks/boxplot_demo/task.yaml`](../../../tasks/boxplot_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml)
- Inputs arity: `2`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string | feature |  |  |  | basic |
| `filename` | 图片文件名 | string |  |  |  | yes | basic |
| `group_dim` | 样本维度 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `groups` | 显示分组顺序 | array |  |  |  |  | basic |
| `point_alpha` | 点透明度 | number | 0.5 | 0 | 1 |  | advanced |
| `point_size` | 点大小 | integer | 4 | 1 |  |  | advanced |
| `show_points` | 显示散点 | boolean | True |  |  |  | advanced |
| `title` | 图标题 | string |  |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `xlabel` | X 轴标题 | string |  |  |  |  | basic |
| `ylabel` | Y 轴标题 | string |  |  |  |  | basic |

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
  "mode": "none"
}
```

## Processing rules (source docstring)

```text
Boxplot of one value column split by groups.

--- module documentation ---

Boxplot of one value column split by groups.

Inputs
------
0. Data form with a value dim (typically the observation dim) and a
   sample dim.
1. Metadata form with the same sample dim and a column that carries
   the group labels.

The sample axis is aligned by label between the two forms. For each
group, one box is drawn for the selected value column.

Domain-agnostic. Any 2D data form + any 2D metadata form works.

Params:
    dim          : dim of the data form that holds the value column
                   (default "feature")
    value_label  : column label to plot (required)
    group_dim    : sample dim shared by both forms (required)
    group_label  : column label on the metadata's other dim
                   (required)
    groups       : optional list of group names to keep, in order
    filename     : output file name (required)
    title        : optional plot title
    xlabel       : optional x label (default: group_label)
    ylabel       : optional y label (default: value_label)
    show_points  : overlay individual points (default True)
    point_size   : marker size for overlay (default 4)
    point_alpha  : marker transparency (default 0.5)
```

## Minimal YAML skeleton

```yaml
- name: boxplot
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    filename: <string>
    group_dim: <string>
    group_label: <string>
    groups: <array>
    point_alpha: <number>
    point_size: <integer>
    show_points: <boolean>
    title: <string>
    value_label: <string>
    xlabel: <string>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/boxplot.md` and regenerate.
