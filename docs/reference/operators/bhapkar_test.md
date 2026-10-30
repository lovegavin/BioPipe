# bhapkar_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/bhapkar_test.py`](../../../src/task/step/steps/bhapkar_test.py)
- Tests: [`tests/test_extension34.py`](../../../tests/test_extension34.py), [`tests/test_r_oracles26.py`](../../../tests/test_r_oracles26.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `row_dim` | Row Dim | string | row |  |  |  | basic |
| `column_dim` | Column Dim | string | column |  |  |  | basic |
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
        "param": "row_dim",
        "default": "row"
      },
      {
        "param": "column_dim",
        "default": "column"
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
Bhapkar test, the Stuart-Maxwell statistic with a finite-sample correction.

--- module documentation ---

Bhapkar test for marginal homogeneity in a square table.
```

## Minimal YAML skeleton

```yaml
- name: bhapkar_test
  inputs: [<input1>]
  params:
    row_dim: <string>
    column_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/bhapkar_test.md` and regenerate.
