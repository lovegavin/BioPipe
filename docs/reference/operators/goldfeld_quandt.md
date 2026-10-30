# goldfeld_quandt

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/goldfeld_quandt.py`](../../../src/task/step/steps/goldfeld_quandt.py)
- Tests: [`tests/test_extension47.py`](../../../tests/test_extension47.py), [`tests/test_r_oracles38.py`](../../../tests/test_r_oracles38.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `variable_dim` | Variable Dim | string | variable |  |  |  | basic |
| `response` | 因变量 | string |  |  |  | yes | basic |
| `regressor` | 自变量 | string |  |  |  | yes | basic |
| `order_by` | 排序变量（默认自变量） | string |  |  |  |  | basic |
| `fraction` | Fraction | number | 0.0 | 0.0 |  |  | basic |
| `alternative` | Alternative | string; enum=['two-sided', 'greater', 'less'] | greater |  |  |  | basic |
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
Goldfeld-Quandt test for heteroskedasticity in a simple linear regression.
```

## Minimal YAML skeleton

```yaml
- name: goldfeld_quandt
  inputs: [<input1>]
  params:
    sample_dim: <string>
    variable_dim: <string>
    response: <string>
    regressor: <string>
    order_by: <string>
    fraction: <number>
    alternative: <string; enum=['two-sided', 'greater', 'less']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/goldfeld_quandt.md` and regenerate.
