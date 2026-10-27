# join

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/join.py`](../../../src/task/step/steps/join.py)
- Tests: [`tasks/join_demo/test_join.py`](../../../tasks/join_demo/test_join.py), [`tasks/multi_omics_route_demo/test_multi_omics_route.py`](../../../tasks/multi_omics_route_demo/test_multi_omics_route.py), [`tasks/verify_multi_omics.py`](../../../tasks/verify_multi_omics.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `columns` | 列 | any | all |  |  |  | basic |
| `how` | 连接方式 | string; enum=['inner', 'left'] | inner |  |  |  | advanced |
| `prefix` | 前缀 | string |  |  |  |  | advanced |

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
    "parallel": [],
    "ndim": 2
  },
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
    "parallel": [],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "project",
  "derived": true,
  "info": {
    "missing_code": {
      "type": [
        "number",
        "null"
      ]
    },
    "representation": {
      "type": "string",
      "const": "joined"
    }
  },
  "labels_unknown": true,
  "axis_info_unknown": true
}
```

## Processing rules (source docstring)

```text
Join two forms along a shared dim by label.

--- module documentation ---

Join two forms along a shared dim by label.

Attaches selected columns from a "metadata" form to a "data" form.
Both forms must have the shared dim as their first axis. The
columns of the metadata form are appended to the data form's second
axis, so the output is a wider form whose labels combine the two.

This is the natural way to bring grouping columns next to the
values they describe, e.g. to color a scatter plot, to split a
barplot, or to feed a violin plot.

Alignment
---------
    inner   keep rows whose label is present in both forms
    left    keep rows whose label is present in the data form,
            filling meta cells with NaN when the row is missing
            from the metadata form

Both forms must be 2D with the shared dim as the first axis. To use
a form whose shared dim is second, transpose it first.

Output
------
    dims    = [shared_dim, <data_other_dim>]
    labels  = {shared_dim:  <common row labels>,
               <data_other_dim>: {<data_feature>: pos,
                                  <selected_meta_column>: pos, ...}}

Feature labels that already exist in the data form are rejected
unless a ``prefix`` is given.

Params:
    dim      : shared dim name (required)
    columns  : list of column labels from the metadata to attach,
               or "all" (default "all")
    how      : "inner" | "left" (default "inner")
    prefix   : optional string prepended to attached column names
    output   : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: join
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    columns: <any>
    how: <string; enum=['inner', 'left']>
    prefix: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/join.md` and regenerate.
