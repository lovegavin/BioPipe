# breusch_pagan

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/breusch_pagan.py`](../../../src/task/step/steps/breusch_pagan.py)
- Tests: [`tests/test_extension13.py`](../../../tests/test_extension13.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `variable_dim` | Variable Dim | string | variable |  |  |  | basic |
| `response` | 响应变量 | string |  |  |  | yes | basic |
| `regressors` | Regressors | array |  |  |  |  | basic |
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
        "param": "variable_dim",
        "default": "variable"
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
Breusch-Pagan heteroskedasticity test for a linear regression.
```

## Minimal YAML skeleton

```yaml
- name: breusch_pagan
  inputs: [<input1>]
  params:
    sample_dim: <string>
    variable_dim: <string>
    response: <string>
    regressors: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/breusch_pagan.md` and regenerate.
