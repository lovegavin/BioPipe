# chi_square_gof

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/chi_square_gof.py`](../../../src/task/step/steps/chi_square_gof.py)
- Tests: [`tests/test_extension45.py`](../../../tests/test_extension45.py), [`tests/test_r_oracles36.py`](../../../tests/test_r_oracles36.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `category_dim` | Category Dim | string | category |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `count_label` | 计数列 | string |  |  |  | yes | basic |
| `expected` | 期望相对频数（留空为均匀分布） | array | [] |  |  |  | basic |
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
        "param": "category_dim",
        "default": "category"
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
One-sample chi-square test against expected relative frequencies.

--- module documentation ---

Pearson chi-square goodness-of-fit test.
```

## Minimal YAML skeleton

```yaml
- name: chi_square_gof
  inputs: [<input1>]
  params:
    category_dim: <string>
    feature_dim: <string>
    count_label: <string>
    expected: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/chi_square_gof.md` and regenerate.
