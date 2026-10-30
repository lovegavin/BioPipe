# zero_inflated_poisson

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/zero_inflated_poisson.py`](../../../src/task/step/steps/zero_inflated_poisson.py)
- Tests: [`tests/test_extension24.py`](../../../tests/test_extension24.py), [`tests/test_r_oracles16.py`](../../../tests/test_r_oracles16.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | Response Label | string |  |  |  | yes | basic |
| `count_predictors` | Count Predictors | array |  |  |  | yes | basic |
| `zero_predictors` | Zero Predictors | array | [] |  |  |  | basic |
| `categorical` | 分类协变量 | array | [] |  |  |  | basic |
| `maxiter` | Maxiter | integer | 200 | 20 |  |  | basic |
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
Poisson count model with a logistic zero-inflation component.

--- module documentation ---

Zero-inflated Poisson regression.
```

## Minimal YAML skeleton

```yaml
- name: zero_inflated_poisson
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    count_predictors: <array>
    zero_predictors: <array>
    categorical: <array>
    maxiter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/zero_inflated_poisson.md` and regenerate.
