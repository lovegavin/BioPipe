# varimax_rotation

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/varimax_rotation.py`](../../../src/task/step/steps/varimax_rotation.py)
- Tests: [`tests/test_extension30.py`](../../../tests/test_extension30.py), [`tests/test_r_oracles22.py`](../../../tests/test_r_oracles22.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `variable_dim` | Variable Dim | string | variable |  |  |  | basic |
| `factor_dim` | Factor Dim | string | factor |  |  |  | basic |
| `normalize` | 行标准化 | boolean | True |  |  |  | basic |
| `eps` | Eps | number | 1e-05 |  |  |  | basic |
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
        "param": "variable_dim",
        "default": "variable"
      },
      {
        "param": "factor_dim",
        "default": "factor"
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
Orthogonal varimax rotation, matching ``stats::varimax``.

--- module documentation ---

Varimax rotation of a loading matrix.
```

## Minimal YAML skeleton

```yaml
- name: varimax_rotation
  inputs: [<input1>]
  params:
    variable_dim: <string>
    factor_dim: <string>
    normalize: <boolean>
    eps: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/varimax_rotation.md` and regenerate.
