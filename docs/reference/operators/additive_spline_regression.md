# additive_spline_regression

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/additive_spline_regression.py`](../../../src/task/step/steps/additive_spline_regression.py)
- Tests: [`tests/test_additive_spline_regression.py`](../../../tests/test_additive_spline_regression.py), [`tests/test_r_oracles78.py`](../../../tests/test_r_oracles78.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | 因变量列 | string |  |  |  | yes | basic |
| `predictors` | 自变量列 | array |  |  |  | yes | basic |
| `df` | B-spline 自由度 | any |  |  |  |  | basic |
| `confidence` | 置信水平 | number | 0.95 |  |  |  | basic |
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
Fit an additive OLS model with one cubic B-spline per predictor.

    The basis uses :func:`patsy.bs`; for a given ``df`` it has the same
    quantile knots as R's ``splines::bs``.  This is an additive model,
    not a penalized GAM: no smoothing parameter is estimated.

--- module documentation ---

Additive regression with cubic B-spline bases.
```

## Minimal YAML skeleton

```yaml
- name: additive_spline_regression
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    predictors: <array>
    df: <any>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/additive_spline_regression.md` and regenerate.
