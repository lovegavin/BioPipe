# distance_correlation

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/distance_correlation.py`](../../../src/task/step/steps/distance_correlation.py)
- Tests: [`tests/test_extension7.py`](../../../tests/test_extension7.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `x_feature_dim` | X Feature Dim | string | feature |  |  |  | basic |
| `y_feature_dim` | Y Feature Dim | string | feature |  |  |  | basic |
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
        "param": "x_feature_dim",
        "default": "feature"
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
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "y_feature_dim",
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
Pairwise distance correlation between two feature matrices.

Distance correlation is zero exactly when two random vectors are independent
(in the population sense), unlike Pearson correlation which only measures
linear association.  The statistic is computed from double-centred Euclidean
distance matrices.
```

## Minimal YAML skeleton

```yaml
- name: distance_correlation
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    x_feature_dim: <string>
    y_feature_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/distance_correlation.md` and regenerate.
