# reduce_axis

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/reduce_axis.py`](../../../src/task/step/steps/reduce_axis.py)
- Tests: [`tasks/reduce_axis_demo/test_reduce_axis.py`](../../../tasks/reduce_axis_demo/test_reduce_axis.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py)
- Demo tasks: [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/filter_by_demo/task.yaml`](../../../tasks/filter_by_demo/task.yaml), [`tasks/reduce_axis_demo/task.yaml`](../../../tasks/reduce_axis_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `stats` | 统计量 | any |  |  |  | yes | basic |

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
      "const": "summary"
    }
  },
  "drop_dims": [
    {
      "param": "dim",
      "default": null
    }
  ],
  "append_dims": [
    {
      "name": "statistic",
      "labels": {
        "param": "stats",
        "default": null
      }
    }
  ]
}
```

## Processing rules (source docstring)

```text
Reduce one axis of a form to summary statistics.

--- module documentation ---

Reduce one axis of a form to summary statistics.

For each position along ``dim``, computes one or more summary
statistics over all other axes, and returns a new form in which
``dim`` is replaced by a ``"statistic"`` axis.

Layout
------
    input  dims: [..., dim, ...]     (any ndim >= 1)
    output dims: [..., "statistic"]  (dim removed)

The reduced dim is removed; every other dim keeps its original
order; the new ``"statistic"`` axis is appended last.

Supported statistics
--------------------
    sum        sum of values
    mean       mean of values
    std        standard deviation
    var        variance
    min        minimum
    max        maximum
    median     median
    nonzero    number of non-zero values
    count      number of non-missing values

Missing cells are identified via ``info["missing_code"]`` when set
and finite, otherwise via NaN. Every statistic except ``count`` and
``nonzero`` excludes missing cells; ``count`` and ``nonzero`` count
only non-missing cells.

Axis-parallel info for the reduced dim (as declared in
``axis_info[dim]``) is dropped from the output. Info entries for
surviving dims pass through unchanged. ``info["encoders"]`` is
trimmed to surviving dims.

Params:
    dim     : dimension to reduce (required)
    stats   : statistic name, or list of names (required)
    output  : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: reduce_axis
  inputs: [<input1>]
  params:
    dim: <string>
    stats: <any>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/reduce_axis.md` and regenerate.
