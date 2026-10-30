# dbscan

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/dbscan.py`](../../../src/task/step/steps/dbscan.py)
- Tests: [`tests/test_extension9.py`](../../../tests/test_extension9.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `eps` | Eps | number | 0.5 |  |  |  | basic |
| `min_samples` | 最少样本数 | integer | 5 | 2 |  |  | basic |
| `metric` | 距离/相关指标 | string; enum=['euclidean', 'manhattan', 'cosine'] | euclidean |  |  |  | advanced |
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
Density-based spatial clustering (DBSCAN).
```

## Minimal YAML skeleton

```yaml
- name: dbscan
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    eps: <number>
    min_samples: <integer>
    metric: <string; enum=['euclidean', 'manhattan', 'cosine']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/dbscan.md` and regenerate.
