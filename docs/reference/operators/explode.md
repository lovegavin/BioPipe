# explode

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/explode.py`](../../../src/task/step/steps/explode.py)
- Tests: [`tasks/explode_demo/test_explode.py`](../../../tasks/explode_demo/test_explode.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/explode_demo/task.yaml`](../../../tasks/explode_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | Dimension to expand | string |  |  |  | yes | basic |
| `field` | Multi-valued field | string |  |  |  | yes | basic |
| `sep` | Separator | string | ; |  |  |  | basic |
| `keep_empty` | Keep empty | boolean | False |  |  |  | basic |
| `output` | Output key | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": [
      {
        "fields": {
          "param": "field",
          "default": null
        },
        "dim": {
          "param": "dim",
          "default": null
        }
      }
    ]
  }
]
```

## Output contract

```json
{
  "mode": "declare",
  "schema": {
    "numeric": true,
    "info_open": true,
    "axis_info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Expand a multi-valued info field into separate positions.

--- module documentation ---

Expand a multi-valued info field into separate positions.

When an info field declared parallel to ``dim`` contains a list per
position (for example semicolon-separated GO terms), this step
creates one output position per element. Other axes are replicated.

This is the standard way to turn a one-to-many annotation into a
long table that downstream grouping operators can consume.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same, with ``dim`` expanded

Params:
    dim        : dimension whose info field is exploded (required)
    field      : info field name declared parallel to ``dim``
                 (required)
    sep        : separator inside each cell (default ";")
    keep_empty : keep positions whose field is empty (default False)
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: explode
  inputs: [<input1>]
  params:
    dim: <string>
    field: <string>
    sep: <string>
    keep_empty: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/explode.md` and regenerate.
