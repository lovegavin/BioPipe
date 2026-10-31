# cusum_chart

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cusum_chart.py`](../../../src/task/step/steps/cusum_chart.py)
- Tests: [`tests/test_extension67.py`](../../../tests/test_extension67.py), [`tests/test_r_oracles58.py`](../../../tests/test_r_oracles58.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `decision_interval` | Decision Interval | number | 5.0 |  |  |  | basic |
| `se_shift` | Se Shift | number | 1.0 |  |  |  | basic |
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
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "feature_dim",
        "default": "feature"
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
Tabular CUSUM chart with a moving-range sigma estimate.

    The chart is a deterministic, table-valued control chart: each output row
    contains the upper/lower CUSUM statistic and the decision limit.  It does
    not draw a plot, so the result can be inspected or plotted by the caller.

--- module documentation ---

Two-sided tabular CUSUM control chart for individual measurements.
```

## Minimal YAML skeleton

```yaml
- name: cusum_chart
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    decision_interval: <number>
    se_shift: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cusum_chart.md` and regenerate.
