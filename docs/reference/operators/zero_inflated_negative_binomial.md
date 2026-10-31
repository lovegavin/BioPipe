# zero_inflated_negative_binomial

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/zero_inflated_negative_binomial.py`](../../../src/task/step/steps/zero_inflated_negative_binomial.py)
- Tests: [`tests/test_extension74.py`](../../../tests/test_extension74.py), [`tests/test_r_oracles64.py`](../../../tests/test_r_oracles64.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | Response Label | string |  |  |  | yes | basic |
| `count_predictors` | Count Predictors | array |  |  |  | yes | basic |
| `zero_predictors` | Zero Predictors | array |  |  |  | yes | basic |
| `categorical` | 分类协变量 | array | [] |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
| `maxiter` | Maxiter | integer | 2000 | 20 |  |  | basic |
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
Zero-inflated NB2 regression with logit inflation and log count links.

--- module documentation ---

Zero-inflated negative binomial regression (NB2).
```

## Minimal YAML skeleton

```yaml
- name: zero_inflated_negative_binomial
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    count_predictors: <array>
    zero_predictors: <array>
    categorical: <array>
    confidence: <number>
    maxiter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/zero_inflated_negative_binomial.md` and regenerate.
