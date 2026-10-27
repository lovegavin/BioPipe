# ma_plot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/ma_plot.py`](../../../src/task/step/steps/ma_plot.py)
- Tests: none found
- Demo tasks: [`tasks/ma_plot_demo/task.yaml`](../../../tasks/ma_plot_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `alpha` | 透明度 | number | 0.7 | 0 | 1 |  | advanced |
| `dim` | 分析维度 | string | gene |  |  |  | basic |
| `filename` | 图片文件名 | string |  |  |  | yes | basic |
| `label_top` | 标记前 N 个特征 | integer | 0 | 0 |  |  | basic |
| `lfc_label` | log2FC 字段 | string | log2FC |  |  |  | basic |
| `mean_a_label` | 对照组均值字段 | string | mean_a |  |  |  | basic |
| `mean_b_label` | 实验组均值字段 | string | mean_b |  |  |  | basic |
| `p_label` | P / Q 字段 | string | P |  |  |  | basic |
| `p_threshold` | 显著性阈值 | number | 0.05 | 0 | 1 |  | basic |
| `point_size` | 点大小 | integer | 8 | 1 |  |  | advanced |
| `stat_dim` | 统计量维度 | string | statistic |  |  |  | advanced |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string | log2 mean |  |  |  | basic |
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
        "default": "gene"
      },
      {
        "param": "stat_dim",
        "default": "statistic"
      }
    ],
    "labels": [
      {
        "dim": {
          "param": "stat_dim",
          "default": "statistic"
        },
        "values": [
          {
            "param": "lfc_label",
            "default": "log2FC"
          },
          {
            "param": "p_label",
            "default": "P"
          },
          {
            "param": "mean_a_label",
            "default": "mean_a"
          },
          {
            "param": "mean_b_label",
            "default": "mean_b"
          }
        ]
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
  "mode": "none"
}
```

## Processing rules (source docstring)

```text
Draw an MA plot.

--- module documentation ---

MA plot of a differential comparison result.

X axis: A = (mean_a + mean_b) / 2
Y axis: M = log2FC
Points are colored by P < p_threshold.

Input is a 2D form with a feature dim and a "statistic" dim that
carries log2FC, mean_a, mean_b, and P.

Params:
    dim           : feature dim (default "gene")
    stat_dim      : statistic dim (default "statistic")
    lfc_label     : column label for log2FC (default "log2FC")
    mean_a_label  : column label for group A mean (default "mean_a")
    mean_b_label  : column label for group B mean (default "mean_b")
    p_label       : column label for P (default "P")
    p_threshold   : P cutoff for significance (default 0.05)
    filename      : output file name (required)
    title         : optional plot title
    xlabel        : optional x label (default "log2 mean")
    ylabel        : optional y label (default: lfc_label)
    point_size    : marker size (default 8)
    alpha         : marker transparency (default 0.7)
    label_top     : if > 0, annotate the top N most significant
                    points with their feature labels (default 0)
```

## Minimal YAML skeleton

```yaml
- name: ma_plot
  inputs: [<input1>]
  params:
    alpha: <number>
    dim: <string>
    filename: <string>
    label_top: <integer>
    lfc_label: <string>
    mean_a_label: <string>
    mean_b_label: <string>
    p_label: <string>
    p_threshold: <number>
    point_size: <integer>
    stat_dim: <string>
    title: <string>
    xlabel: <string>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/ma_plot.md` and regenerate.
