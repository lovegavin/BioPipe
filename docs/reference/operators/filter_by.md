# filter_by

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/filter_by.py`](../../../src/task/step/steps/filter_by.py)
- Tests: [`tasks/filter_by_demo/test_filter_by.py`](../../../tasks/filter_by_demo/test_filter_by.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/filter_by_demo/task.yaml`](../../../tasks/filter_by_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `rules` | 过滤规则 | array |  |  |  | yes | basic |

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
    "parallel": []
  },
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      },
      "statistic"
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
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Keep positions along a dim that satisfy thresholds from another form.

--- module documentation ---

Filter one axis of a form using thresholds on a second form.

Two inputs share a dim (the filter dim). The first input is the data
form; the second is a metrics form whose positions along the shared
dim carry one or more statistics. The operator keeps, along the data
form's shared dim, only the positions that satisfy every rule.

Layout
------
    data     dims: [..., dim, ...]   (any ndim >= 1)
    metrics  dims: [dim, "statistic"]   (2D)
    output   dims: same as data, but dim is subset

Rules
-----
Each rule is a mapping:

    {field: <name>, min: <float>}   keep positions with value >= min
    {field: <name>, max: <float>}   keep positions with value <= max
    {field: <name>, min: <float>, max: <float>}   both

``field`` must be a label on the metrics form's ``statistic`` dim.
The metrics form's ``dim`` labels must all appear in the data form's
``dim`` labels; extra positions on either side are ignored.

Missing values
--------------
A missing value in the metrics form never satisfies a min/max rule;
the position is dropped, and the drop is recorded in the export.

Params:
    dim      : shared dim name (required)
    rules    : list of rule mappings (required, non-empty)
    output   : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: filter_by
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    rules: <array>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/filter_by.md` and regenerate.
