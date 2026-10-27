# forest_plot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/forest_plot.py`](../../../src/task/step/steps/forest_plot.py)
- Tests: none found
- Demo tasks: [`tasks/forest_plot_demo/task.yaml`](../../../tasks/forest_plot_demo/task.yaml), [`tasks/survival_demo/task.yaml`](../../../tasks/survival_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `color_ns` | color_ns | string | #4C72B0 |  |  |  | basic |
| `color_sig` | color_sig | string | #D62728 |  |  |  | basic |
| `dim` | 分析维度 | string | covariate |  |  |  | basic |
| `filename` | 图片文件名 | string |  |  |  | yes | basic |
| `high_label` | CI 上界字段 | string | CI_high |  |  |  | basic |
| `hr_label` | HR 字段 | string | HR |  |  |  | basic |
| `log_scale` | Log 坐标 | boolean | True |  |  |  | basic |
| `low_label` | CI 下界字段 | string | CI_low |  |  |  | basic |
| `p_label` | P / Q 字段 | string | P |  |  |  | basic |
| `sort_by` | 排序 | any; enum=['input', 'hr', 'p'] | input |  |  |  | basic |
| `stat_dim` | 统计量维度 | string | statistic |  |  |  | advanced |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string | Hazard ratio (95% CI) |  |  |  | basic |
| `xlim` | X 轴范围 | object / array |  |  |  |  | basic |

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
        "default": "covariate"
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
            "param": "hr_label",
            "default": "HR"
          },
          {
            "param": "low_label",
            "default": "CI_low"
          },
          {
            "param": "high_label",
            "default": "CI_high"
          },
          {
            "param": "p_label",
            "default": "P"
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
Draw a forest plot of hazard ratios.

--- module documentation ---

Forest plot of hazard ratios from a Cox regression result.

Input is the 2D form produced by ``cox_regression``: one row per
covariate, one column per statistic. The operator draws a horizontal
forest plot with one line per covariate, showing the point estimate
of HR and its 95% confidence interval.

The reference line is HR = 1 (log scale). Covariates whose CI does
not cross the reference line are highlighted.

Params:
    dim         : covariate dim (default "covariate")
    stat_dim    : statistic dim (default "statistic")
    hr_label    : column with HR (default "HR")
    low_label   : column with lower CI (default "CI_low")
    high_label  : column with upper CI (default "CI_high")
    p_label     : column with p-value (default "P")
    filename    : output file name (required)
    title       : optional plot title
    xlabel      : optional x-label (default "Hazard ratio (95% CI)")
    xlim        : optional [x_min, x_max] on the HR scale
    log_scale   : use log scale on x (default True)
    color_sig   : color for significant rows (default "#D62728")
    color_ns    : color for non-significant rows (default "#4C72B0")
    sort_by    : "input" | "hr" | "p" (default "input")
```

## Minimal YAML skeleton

```yaml
- name: forest_plot
  inputs: [<input1>]
  params:
    color_ns: <string>
    color_sig: <string>
    dim: <string>
    filename: <string>
    high_label: <string>
    hr_label: <string>
    log_scale: <boolean>
    low_label: <string>
    p_label: <string>
    sort_by: <any; enum=['input', 'hr', 'p']>
    stat_dim: <string>
    title: <string>
    xlabel: <string>
    xlim: <object / array>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/forest_plot.md` and regenerate.
