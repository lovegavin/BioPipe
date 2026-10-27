# annotate

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/annotate.py`](../../../src/task/step/steps/annotate.py)
- Tests: [`tasks/annotate_demo/test_annotate.py`](../../../tasks/annotate_demo/test_annotate.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/annotate_demo/task.yaml`](../../../tasks/annotate_demo/task.yaml), [`tasks/order_axis_demo/task.yaml`](../../../tasks/order_axis_demo/task.yaml), [`tasks/prioritize_demo/task.yaml`](../../../tasks/prioritize_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `target_dim` | Target key dimension | string |  |  |  | yes | basic |
| `source_dim` | Reference key dimension | string |  |  |  | yes | basic |
| `fields` | Fields to attach | array |  |  |  | yes | basic |
| `field_dim` | Reference field dimension | string |  |  |  |  | advanced |
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
        "param": "target_dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  },
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "source_dim",
        "default": null
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
  "mode": "unknown"
}
```

## Processing rules (source docstring)

```text
Attach reference fields onto a target by key label.

--- module documentation ---

Attach reference fields onto a target by key label.

Aligns two forms on a shared key dimension by label, then copies the
requested reference fields into the target's ``info``, declaring them
parallel to the target key axis.

A reference field may come from either:

* a data column: its label on ``field_dim``; encoded columns carry
  their encoder across so codes stay comparable.
* an info field: declared parallel to ``source_dim`` in
  ``axis_info``; typically read verbatim by ``info_columns``.

This is the standard way to enrich a table with an external lookup
table (variant annotations, gene descriptions, taxon metadata,
sample covariates) without merging data dimensions.

Layout
------
    target     dims: [key_dim, ...]
    reference  dims: [key_dim_ref, field_dim]
    output     dims: same as target

Alignment
---------
Matching is by label, not by position. For every target label on
``target_dim``, the reference row whose ``source_dim`` label equals
it supplies the values. Target labels without a reference match get
NaN.

The alignment is computed once as a position lookup array and applied
with numpy fancy indexing, so the cost is O(n) in C, not in Python.

Params:
    target_dim : key dimension on the target (required)
    source_dim : key dimension on the reference (required)
    fields     : reference field names to attach (required)
    field_dim  : reference data dimension (default: the other 2D dim)
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: annotate
  inputs: [<input1>, <input2>]
  params:
    target_dim: <string>
    source_dim: <string>
    fields: <array>
    field_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/annotate.md` and regenerate.
