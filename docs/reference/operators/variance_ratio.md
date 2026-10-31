# variance_ratio

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/variance_ratio.py`](../../../src/task/step/steps/variance_ratio.py)
- Tests: [`tests/test_extension58.py`](../../../tests/test_extension58.py), [`tests/test_r_oracles49.py`](../../../tests/test_r_oracles49.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `value_dim` | Value Dim | string | value |  |  |  | basic |
| `first_label` | First Label | string |  |  |  |  | basic |
| `second_label` | Second Label | string |  |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two-sided', 'less', 'greater'] | two-sided |  |  |  | basic |
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
        "param": "value_dim",
        "default": "value"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  },
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
        "param": "value_dim",
        "default": "value"
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
F test for the ratio of two independent variances.
```

## Minimal YAML skeleton

```yaml
- name: variance_ratio
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    value_dim: <string>
    first_label: <string>
    second_label: <string>
    alternative: <string; enum=['two-sided', 'less', 'greater']>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/variance_ratio.md` and regenerate.
