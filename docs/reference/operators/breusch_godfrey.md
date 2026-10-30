# breusch_godfrey

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/breusch_godfrey.py`](../../../src/task/step/steps/breusch_godfrey.py)
- Tests: [`tests/test_extension22.py`](../../../tests/test_extension22.py), [`tests/test_r_oracles14.py`](../../../tests/test_r_oracles14.py)
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
| `lags` | Lags | integer | 1 | 1 |  |  | basic |
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
    "info_open": false,
    "axis_info_open": false,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    }
  }
}
```

## Processing rules (source docstring)

```text
Breusch-Godfrey serial-correlation test for an OLS regression.
```

## Minimal YAML skeleton

```yaml
- name: breusch_godfrey
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    predictors: <array>
    categorical: <array>
    lags: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/breusch_godfrey.md` and regenerate.
