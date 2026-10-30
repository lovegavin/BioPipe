# holm_adjust

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/holm_adjust.py`](../../../src/task/step/steps/holm_adjust.py)
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py), [`tests/test_r_oracles2.py`](../../../tests/test_r_oracles2.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_dim` | Value Dim | string | pvalue |  |  |  | basic |
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
        "param": "feature_dim",
        "default": "feature"
      },
      {
        "param": "value_dim",
        "default": "statistic"
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
Holm step-down p-value adjustment; output feature x qvalue.

--- module documentation ---

Holm step-down family-wise error adjustment.
```

## Minimal YAML skeleton

```yaml
- name: holm_adjust
  inputs: [<input1>]
  params:
    feature_dim: <string>
    value_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/holm_adjust.md` and regenerate.
