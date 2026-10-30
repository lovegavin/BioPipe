# linear_mixed_model

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/linear_mixed_model.py`](../../../src/task/step/steps/linear_mixed_model.py)
- Tests: [`tests/test_extension14.py`](../../../tests/test_extension14.py), [`tests/test_r_oracles6.py`](../../../tests/test_r_oracles6.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | Response Label | string |  |  |  | yes | basic |
| `fixed_effects` | Fixed Effects | array |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `categorical` | 分类协变量 | array |  |  |  |  | basic |
| `reml` | Reml | boolean | True |  |  |  | basic |
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
Random-intercept linear mixed model via statsmodels MixedLM.

--- module documentation ---

Linear mixed-effects model with a random intercept.
```

## Minimal YAML skeleton

```yaml
- name: linear_mixed_model
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    fixed_effects: <array>
    group_label: <string>
    categorical: <array>
    reml: <boolean>
    maxiter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/linear_mixed_model.md` and regenerate.
