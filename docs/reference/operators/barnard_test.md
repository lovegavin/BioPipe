# barnard_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/barnard_test.py`](../../../src/task/step/steps/barnard_test.py)
- Tests: [`tests/test_extension43.py`](../../../tests/test_extension43.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `row_dim` | Row Dim | string | row |  |  |  | basic |
| `column_dim` | Column Dim | string | column |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two-sided', 'less', 'greater'] | two-sided |  |  |  | basic |
| `pooled` | Pooled | boolean | True |  |  |  | basic |
| `integration_points` | Integration Points | integer | 32 | 1 | 4096 |  | basic |
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
    "ndim": 1,
    "numeric": true,
    "info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Barnard's exact unconditional test of independence in a 2x2 table.

    The p-value is computed with SciPy's unconditional exact algorithm,
    which maximises over the nuisance success probability.

--- module documentation ---

Barnard exact unconditional test for a 2x2 table.
```

## Minimal YAML skeleton

```yaml
- name: barnard_test
  inputs: [<input1>]
  params:
    row_dim: <string>
    column_dim: <string>
    alternative: <string; enum=['two-sided', 'less', 'greater']>
    pooled: <boolean>
    integration_points: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/barnard_test.md` and regenerate.
