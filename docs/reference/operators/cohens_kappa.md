# cohens_kappa

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cohens_kappa.py`](../../../src/task/step/steps/cohens_kappa.py)
- Tests: [`tests/test_extension13.py`](../../../tests/test_extension13.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `row_dim` | Row Dim | string | rater_a |  |  |  | basic |
| `col_dim` | Col Dim | string | rater_b |  |  |  | basic |
| `weights` | Weights | string; enum=['none', 'linear', 'quadratic'] | none |  |  |  | basic |
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
        "default": "rater_a"
      },
      {
        "param": "col_dim",
        "default": "rater_b"
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
Cohen's kappa for two raters on a contingency table.
```

## Minimal YAML skeleton

```yaml
- name: cohens_kappa
  inputs: [<input1>]
  params:
    row_dim: <string>
    col_dim: <string>
    weights: <string; enum=['none', 'linear', 'quadratic']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cohens_kappa.md` and regenerate.
