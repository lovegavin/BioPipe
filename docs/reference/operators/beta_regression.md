# beta_regression

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/beta_regression.py`](../../../src/task/step/steps/beta_regression.py)
- Tests: [`tests/test_extension71.py`](../../../tests/test_extension71.py), [`tests/test_r_oracles62.py`](../../../tests/test_r_oracles62.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | Response Label | string |  |  |  | yes | basic |
| `predictors` | Predictors | array |  |  |  | yes | basic |
| `categorical` | 分类协变量 | array | [] |  |  |  | basic |
| `max_iter` | Max Iter | integer | 500 | 20 |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
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
Beta regression with a logit mean link and identity precision link.

--- module documentation ---

Beta regression for response values strictly between zero and one.
```

## Minimal YAML skeleton

```yaml
- name: beta_regression
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    predictors: <array>
    categorical: <array>
    max_iter: <integer>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/beta_regression.md` and regenerate.
