# stuart_maxwell

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/stuart_maxwell.py`](../../../src/task/step/steps/stuart_maxwell.py)
- Tests: [`tests/test_extension14.py`](../../../tests/test_extension14.py), [`tests/test_r_oracles6.py`](../../../tests/test_r_oracles6.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `rater_a` | Rater A | string |  |  |  | yes | basic |
| `rater_b` | Rater B | string |  |  |  | yes | basic |
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
Test whether two raters have the same marginal distribution.

--- module documentation ---

Stuart-Maxwell test for marginal homogeneity in a square table.
```

## Minimal YAML skeleton

```yaml
- name: stuart_maxwell
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    rater_a: <string>
    rater_b: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/stuart_maxwell.md` and regenerate.
