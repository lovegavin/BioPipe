# aggregate

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/aggregate.py`](../../../src/task/step/steps/aggregate.py)
- Tests: [`tasks/aggregate_demo/test_aggregate.py`](../../../tasks/aggregate_demo/test_aggregate.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/aggregate_demo/task.yaml`](../../../tasks/aggregate_demo/task.yaml), [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `group_col` | 分析维度 | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['sum', 'mean', 'median', 'min', 'max', 'count'] | sum |  |  |  | basic |

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
    "ndim": 2,
    "labels_axis": [
      {
        "axis": 1,
        "values": [
          {
            "param": "group_col",
            "default": null
          }
        ]
      }
    ]
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
      "const": "aggregate"
    }
  },
  "drop_dims": [
    {
      "param": "dim",
      "default": null
    }
  ],
  "prepend_dims": [
    {
      "input_axis": [
        1,
        1
      ]
    }
  ]
}
```

## Processing rules (source docstring)

```text
Aggregate positions along one axis by group.

--- module documentation ---

Aggregate positions along one axis by group.

Two inputs share an axis (the "row" axis). The first input carries
values; the second carries a group label for each position. For
each group, the operator collapses all positions in that group
into a single row by applying a reduction (sum, mean, median, ...).

This is the natural companion of ``join``: where ``join`` attaches
metadata columns to a form, ``aggregate`` reduces a form by a
metadata column. Typical uses:

    - collapse species to genus before plotting composition
    - collapse cells to clusters before profiling
    - collapse genes to pathways before scoring
    - collapse any [row, other] matrix by a [row, group] table

Layout
------
    data    dims: [row_dim, other_dim]   (any two axes)
    groups  dims: [row_dim, group_dim]   (same row_dim first)
    output  dims: [group_dim, other_dim]

Both inputs must be 2D with ``dim`` as their first axis. To use a
form whose shared axis is second, transpose it first.

Reductions
----------
    sum       sum of values in the group
    mean      mean of values in the group
    median    median of values in the group
    min       minimum
    max       maximum
    count     number of non-missing values in the group

Missing cells are excluded before the reduction, except for
``count`` where they are dropped from the count.

Group labels
------------
The group column can be a numeric column (each value is used as a
group key) or an encoded string column (the encoder's inverse map
is used to recover group names). The output group labels are the
recovered names, sorted by first appearance in the input order.

Params:
    dim        : shared dim name (required)
    group_col  : column label on the groups form (required)
    method     : reduction name (default "sum")
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: aggregate
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    group_col: <string>
    method: <string; enum=['sum', 'mean', 'median', 'min', 'max', 'count']>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/aggregate.md` and regenerate.
