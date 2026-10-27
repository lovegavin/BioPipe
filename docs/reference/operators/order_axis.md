# order_axis

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/order_axis.py`](../../../src/task/step/steps/order_axis.py)
- Tests: [`tasks/order_axis_demo/test_order_axis.py`](../../../tasks/order_axis_demo/test_order_axis.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/order_axis_demo/task.yaml`](../../../tasks/order_axis_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | Dimension to reorder | string |  |  |  | yes | basic |
| `by` | Ordering field | string |  |  |  | yes | basic |
| `descending` | Descending | boolean | False |  |  |  | basic |
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
  "mode": "unknown"
}
```

## Processing rules (source docstring)

```text
Reorder an axis by a numeric info field, keeping all positions.

--- module documentation ---

Reorder every position along an axis by an info field.

Unlike ``prioritize``, which keeps only the top N positions,
``order_axis`` keeps every position and only changes their order.
The set of labels is unchanged; their positions along ``dim`` are
reassigned according to the ranking.

Typical uses: sort variants by genomic position before plotting,
sort samples by a covariate, sort features by variance before a
heatmap.

Layout
------
    input   dims: [..., dim, ...]
    output  dims: same as input, ``dim`` reordered

Params:
    dim        : dimension to reorder (required)
    by         : numeric info field declared parallel to ``dim``
                 (required)
    descending : True ranks largest first; False ranks smallest
                 first (default)
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: order_axis
  inputs: [<input1>]
  params:
    dim: <string>
    by: <string>
    descending: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/order_axis.md` and regenerate.
