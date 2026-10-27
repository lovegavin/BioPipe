# bin

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/bin.py`](../../../src/task/step/steps/bin.py)
- Tests: [`tasks/bin_demo/test_bin.py`](../../../tasks/bin_demo/test_bin.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `bins` | 分箱数 | integer | 10 | 1 |  |  | basic |
| `method` | 方法 | string; enum=['quantile', 'uniform'] | quantile |  |  |  | basic |
| `value_label` | 分析维度 | string |  |  |  |  | basic |
| `stat` | Stat | string; enum=['mean', 'median', 'min', 'max', 'first'] | mean |  |  |  | basic |

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
      "const": "bins"
    }
  },
  "keep_dims": [
    {
      "param": "dim",
      "default": null
    }
  ],
  "append_dims": [
    {
      "name": "bin",
      "labels": [
        "bin"
      ]
    }
  ]
}
```

## Processing rules (source docstring)

```text
Discretize a continuous axis into bins.

--- module documentation ---

Discretize a continuous axis into bins.

For each position along ``dim``, computes a bin index by cutting the
values along the other axes into equal-width or equal-frequency
intervals. The output has one row per position along ``dim`` and a
single integer bin id per row.

This is the standard way to turn a continuous quantity (age,
expression, allele frequency, distance) into a categorical one that
can be used by grouping operators such as ``aggregate`` or
``compare_groups``.

Value per position
------------------
Two ways to decide the value used to bin each position:

1. ``value_label`` : if given, the operator reads that column from
   the "other" axis (the one that is not ``dim``) and uses its
   values directly. This is the right choice when the input is a
   table whose second axis is a "statistic" axis with a single
   named column.

2. ``stat`` : if ``value_label`` is not given, the operator
   summarizes each position's values along the other axes with one
   of the following statistics:

       mean      mean over the other axes (default)
       median    median over the other axes
       min       minimum
       max       maximum
       first     first non-missing value

Missing cells are excluded from the summary.

Methods
-------
    quantile  equal-frequency bins: each bin holds roughly the same
              number of positions (default)
    uniform   equal-width bins: the value range is split into N
              equal intervals

Layout
------
    input   dims: [..., dim, ...]  (any ndim >= 1)
    output  dims: [dim, "bin"]

NaNs and out-of-range values
----------------------------
Positions whose value is NaN get bin id -1. Positions outside the
observed range (only possible with ``uniform``) get clamped to the
nearest bin.

Params:
    dim          : dimension to bin along (required)
    bins         : number of bins (default 10)
    method       : "quantile" | "uniform" (default "quantile")
    value_label  : optional column label on the other axis; if
                   given, that column's values are used directly
    stat         : summary name (default "mean"), ignored when
                   ``value_label`` is given
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: bin
  inputs: [<input1>]
  params:
    dim: <string>
    bins: <integer>
    method: <string; enum=['quantile', 'uniform']>
    value_label: <string>
    stat: <string; enum=['mean', 'median', 'min', 'max', 'first']>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/bin.md` and regenerate.
