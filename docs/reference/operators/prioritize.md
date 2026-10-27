# prioritize

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/prioritize.py`](../../../src/task/step/steps/prioritize.py)
- Tests: [`tasks/prioritize_demo/test_prioritize.py`](../../../tasks/prioritize_demo/test_prioritize.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/prioritize_demo/task.yaml`](../../../tasks/prioritize_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | Dimension to sort | string |  |  |  | yes | basic |
| `by` | Ranking field | string |  |  |  | yes | basic |
| `top_n` | Top N | integer |  | 1 |  | yes | basic |
| `ascending` | Ascending | boolean | False |  |  |  | basic |
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
          "param": "by",
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
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Keep the top positions along a dimension, ranked by an info field.

--- module documentation ---

Keep the top positions along an axis, ranked by an info field.

Positions are sorted by a numeric info field declared parallel to
``dim``. The top ``top_n`` are retained. Their order in the output
matches their order in the source, so downstream label alignment
stays stable.

This pairs with ``annotate``: annotate writes reference columns into
``info``; prioritize selects the positions whose annotation matters
most.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same as input, with ``dim`` shortened to ``top_n``

Ranking
-------
Missing values (NaN) are ranked last regardless of direction.
Ties keep their source order (stable sort).

Params:
    dim        : dimension to sort along (required)
    by         : info field to rank by (required)
    top_n      : number of positions to keep (required)
    ascending  : False ranks largest first (default); True ranks
                 smallest first
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: prioritize
  inputs: [<input1>]
  params:
    dim: <string>
    by: <string>
    top_n: <integer>
    ascending: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/prioritize.md` and regenerate.
