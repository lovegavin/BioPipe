# interval_censored_regression

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/interval_censored_regression.py`](../../../src/task/step/steps/interval_censored_regression.py)
- Tests: [`tests/test_interval_censored_regression.py`](../../../tests/test_interval_censored_regression.py), [`tests/test_r_oracles81.py`](../../../tests/test_r_oracles81.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `time_lower_label` | 区间下界列 | string |  |  |  | yes | basic |
| `time_upper_label` | 区间上界列 | string |  |  |  | yes | basic |
| `covariates` | 自变量列 | array |  |  |  | yes | basic |
| `confidence` | 置信水平 | number | 0.95 |  |  |  | basic |
| `max_iter` | 最大迭代次数 | integer | 500 | 50 | 2000 |  | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "feature_dim",
        "default": "feature"
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
  "mode": "declare",
  "schema": {
    "ndim": 2,
    "numeric": true,
    "info_open": true,
    "axis_info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Fit a Weibull AFT model to interval-censored observations.

    Each row supplies a lower and upper observation time.  ``lower < upper``
    is an interval, ``lower == upper`` is exact, ``upper = inf`` is right
    censored, and ``lower <= 0`` is left censored.  The likelihood is the
    interval probability under a Weibull AFT model, the same model fitted by
    R's ``survival::survreg(..., dist="weibull")`` for interval2 responses.

--- module documentation ---

Weibull accelerated failure-time regression for interval-censored data.
```

## Minimal YAML skeleton

```yaml
- name: interval_censored_regression
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    time_lower_label: <string>
    time_upper_label: <string>
    covariates: <array>
    confidence: <number>
    max_iter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/interval_censored_regression.md` and regenerate.
