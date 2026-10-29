# fisher_exact

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/fisher_exact.py`](../../../src/task/step/steps/fisher_exact.py)
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `row_dim` | Row Dim | string | row |  |  |  | basic |
| `col_dim` | Col Dim | string | col |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two-sided', 'less', 'greater'] | two-sided |  |  |  | basic |
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
        "param": "col_dim",
        "default": "col"
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
Fisher exact test for a 2x2 contingency table.
```

## Minimal YAML skeleton

```yaml
- name: fisher_exact
  inputs: [<input1>]
  params:
    row_dim: <string>
    col_dim: <string>
    alternative: <string; enum=['two-sided', 'less', 'greater']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/fisher_exact.md` and regenerate.
