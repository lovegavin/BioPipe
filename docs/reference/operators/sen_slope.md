# sen_slope

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/sen_slope.py`](../../../src/task/step/steps/sen_slope.py)
- Tests: [`tests/test_extension39.py`](../../../tests/test_extension39.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `x_label` | 自变量字段 | string |  |  |  | yes | basic |
| `y_label` | 因变量字段 | string |  |  |  | yes | basic |
| `confidence` | 置信水平 | number | 0.95 | 0.0 | 1.0 |  | basic |
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
Sen's median pairwise slope with a Theil-Sen confidence interval.

    ``scipy.stats.theilslopes`` is the reference implementation: it forms all
    pairwise slopes, takes the median, and uses the rank-based confidence
    interval.

--- module documentation ---

Sen's slope and Theil-Sen intercept from paired observations.
```

## Minimal YAML skeleton

```yaml
- name: sen_slope
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    x_label: <string>
    y_label: <string>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/sen_slope.md` and regenerate.
