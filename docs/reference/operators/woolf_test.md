# woolf_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/woolf_test.py`](../../../src/task/step/steps/woolf_test.py)
- Tests: [`tests/test_extension33.py`](../../../tests/test_extension33.py), [`tests/test_r_oracles25.py`](../../../tests/test_r_oracles25.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `stratum_dim` | Stratum Dim | string | stratum |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `a_label` | A：标签 | string | a |  |  |  | basic |
| `b_label` | B：标签 | string | b |  |  |  | basic |
| `c_label` | C Label | string | c |  |  |  | basic |
| `d_label` | D Label | string | d |  |  |  | basic |
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
        "param": "stratum_dim",
        "default": "stratum"
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
Woolf test for homogeneity of odds ratios across 2x2 strata.

--- module documentation ---

Woolf test for homogeneity of odds ratios.
```

## Minimal YAML skeleton

```yaml
- name: woolf_test
  inputs: [<input1>]
  params:
    stratum_dim: <string>
    feature_dim: <string>
    a_label: <string>
    b_label: <string>
    c_label: <string>
    d_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/woolf_test.md` and regenerate.
