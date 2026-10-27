# logrank_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/logrank_test.py`](../../../src/task/step/steps/logrank_test.py)
- Tests: [`tasks/logrank_test_demo/test_logrank_test.py`](../../../tasks/logrank_test_demo/test_logrank_test.py), [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/logrank_test_demo/task.yaml`](../../../tasks/logrank_test_demo/task.yaml), [`tasks/survival_demo/task.yaml`](../../../tasks/survival_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `event_label` | 事件字段 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_map` | 分组映射 | object / array |  |  |  |  | basic |
| `groups` | 显示分组顺序 | array |  |  |  |  | basic |
| `pairwise` | 两两比较 | boolean | False |  |  |  | basic |
| `time_label` | 随访时间字段 | string |  |  |  | yes | basic |

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
  "mode": "logrank_test"
}
```

## Processing rules (source docstring)

```text
Log-rank test for survival differences across groups.

--- module documentation ---

Log-rank test on survival data grouped by a label column.

Compares survival distributions across groups. Statistics are
delegated to lifelines:

    multivariate_logrank_test   overall test across all groups
    logrank_test                pairwise test between two groups

Input is a single 2D form with samples as rows and clinical
variables as columns.

Output form
-----------
    dims    = ["comparison", "statistic"]
    labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
               statistic: {"chi2": 0, "df": 1, "P": 2}}

Params:
    time_label   : follow-up time (required)
    event_label  : event indicator, 1 = event, 0 = censored (required)
    group_label  : group assignment (required)
    group_map    : optional dict {raw: display} to remap group values
    groups       : optional list of group names to keep, in order
    pairwise     : also run pairwise comparisons (default False,
                   only used when there are >= 3 groups)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: logrank_test
  inputs: [<input1>]
  params:
    event_label: <string>
    group_label: <string>
    group_map: <object / array>
    groups: <array>
    pairwise: <boolean>
    time_label: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/logrank_test.md` and regenerate.
