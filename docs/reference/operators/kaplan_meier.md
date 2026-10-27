# kaplan_meier

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/kaplan_meier.py`](../../../src/task/step/steps/kaplan_meier.py)
- Tests: none found
- Demo tasks: [`tasks/kaplan_meier_demo/task.yaml`](../../../tasks/kaplan_meier_demo/task.yaml), [`tasks/survival_demo/task.yaml`](../../../tasks/survival_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `event_label` | 事件字段 | string |  |  |  | yes | basic |
| `filename` | 图片文件名 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_map` | 分组映射 | object / array |  |  |  |  | basic |
| `groups` | 显示分组顺序 | array |  |  |  |  | basic |
| `show_censors` | 显示删失标记 | boolean | True |  |  |  | basic |
| `show_ci` | 显示置信区间 | boolean | False |  |  |  | basic |
| `time_label` | 随访时间字段 | string |  |  |  | yes | basic |
| `title` | 图标题 | string |  |  |  |  | basic |
| `xlabel` | X 轴标题 | string | Time |  |  |  | basic |
| `xlim` | X 轴范围 | object / array |  |  |  |  | basic |
| `ylabel` | Y 轴标题 | string | Survival probability |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_axis": [
      {
        "axis": 1,
        "values": [
          {
            "param": "time_label",
            "default": null
          },
          {
            "param": "event_label",
            "default": null
          },
          {
            "param": "group_label",
            "default": null
          }
        ]
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
Draw Kaplan-Meier survival curves.

--- module documentation ---

Kaplan-Meier survival curves.

Input is a single 2D form with rows = samples and columns = clinical
variables. The operator reads three columns, groups samples by the
group column, and draws one survival curve per group.

Group values can be remapped before plotting via ``group_map``.
This is the standard way to collapse substages (``Stage IA``,
``Stage IIB``) into main stages (``Stage I``, ``Stage II``), or to
merge any set of raw labels into a smaller set of display groups.

Params:
    time_label    : column with follow-up time (required)
    event_label   : column with event indicator (required)
    group_label   : column with group assignment (required)
    group_map     : optional dict {raw_value: display_value}. Raw
                    values not in the dict are kept as-is.
    groups        : optional list of display group names to keep,
                    in output order
    filename      : output file name (required)
    title         : optional plot title
    xlabel        : optional x-label (default "Time")
    ylabel        : optional y-label (default "Survival probability")
    show_censors  : mark censored observations (default True)
    show_ci       : draw pointwise confidence bands (default False)
    xlim          : optional [x_min, x_max]
```

## Minimal YAML skeleton

```yaml
- name: kaplan_meier
  inputs: [<input1>]
  params:
    event_label: <string>
    filename: <string>
    group_label: <string>
    group_map: <object / array>
    groups: <array>
    show_censors: <boolean>
    show_ci: <boolean>
    time_label: <string>
    title: <string>
    xlabel: <string>
    xlim: <object / array>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/kaplan_meier.md` and regenerate.
