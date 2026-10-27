# cox_regression

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/cox_regression.py`](../../../src/task/step/steps/cox_regression.py)
- Tests: [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/cox_regression_demo/task.yaml`](../../../tasks/cox_regression_demo/task.yaml), [`tasks/forest_plot_demo/task.yaml`](../../../tasks/forest_plot_demo/task.yaml), [`tasks/survival_demo/task.yaml`](../../../tasks/survival_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `categorical` | 分类协变量 | array | [] |  |  |  | basic |
| `covariates` | 协变量 | array |  |  |  | yes | basic |
| `event_label` | 事件字段 | string |  |  |  | yes | basic |
| `time_label` | 随访时间字段 | string |  |  |  | yes | basic |
| `weights_label` | 权重字段 | string |  |  |  |  | basic |

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
          }
        ]
      },
      {
        "axis": 1,
        "values": {
          "param": "covariates",
          "default": []
        }
      }
    ]
  }
]
```

## Output contract

```json
{
  "mode": "cox_regression"
}
```

## Processing rules (source docstring)

```text
Fit a Cox proportional hazards model.

--- module documentation ---

Cox proportional hazards regression.

Input is a single 2D form with samples as rows and clinical
variables as columns. The operator reads a time column, an event
column, and a set of covariate columns, then fits a Cox proportional
hazards model.

Statistics are delegated to lifelines.CoxPHFitter.

Output form
-----------
    dims    = ["covariate", "statistic"]
    labels  = {covariate: {name: i},
               statistic: {"coef": 0, "HR": 1, "se": 2,
                           "z": 3, "P": 4,
                           "CI_low": 5, "CI_high": 6}}

Categorical covariates
----------------------
String-valued columns (or those encoded by a Reader) are expanded
into one binary column per level, dropping the first level as the
reference. The covariate label in the output is "{col}_{level}".
Numeric columns pass through unchanged.

Params:
    time_label   : column with follow-up time (required)
    event_label  : column with event indicator (required)
    covariates   : list of column names to use as predictors
                   (required)
    categorical  : list of covariate names to treat as categorical;
                   others are used as-is (optional)
    weights_label: optional column with sample weights
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: cox_regression
  inputs: [<input1>]
  params:
    categorical: <array>
    covariates: <array>
    event_label: <string>
    time_label: <string>
    weights_label: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cox_regression.md` and regenerate.
