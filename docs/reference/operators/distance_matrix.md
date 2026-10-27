# distance_matrix

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/distance_matrix.py`](../../../src/task/step/steps/distance_matrix.py)
- Tests: [`tasks/distance_matrix_demo/test_distance_matrix.py`](../../../tasks/distance_matrix_demo/test_distance_matrix.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py)
- Demo tasks: [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/distance_matrix_demo/task.yaml`](../../../tasks/distance_matrix_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `metric` | 距离/相关指标 | string; enum=['euclidean', 'manhattan', 'cosine', 'correlation', 'braycurtis', 'jaccard', 'hamming'] | euclidean |  |  |  | advanced |
| `max_positions` | 最大位置数 | integer / null | None | 1 |  |  | basic |

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
      "const": "distance"
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
      "name": {
        "param": "dim",
        "suffix": "_b"
      },
      "labels_from": {
        "param": "dim",
        "default": null
      }
    }
  ]
}
```

## Processing rules (source docstring)

```text
Pairwise distance matrix along one axis.

--- module documentation ---

Pairwise distance matrix along one axis of a form.

Computes the distance between every pair of positions along ``dim``,
using the values across the other axes as features. The output is a
square form with the same labels on both axes.

Output dims
-----------
    dims = [dim, f"{dim}_b"]

Both axes carry the same labels, in the same order. ``form.data[i, j]``
is the distance between position ``i`` and position ``j``.

Metrics
-------
    euclidean     L2 distance
    manhattan     L1 distance
    cosine        1 - cosine similarity
    correlation   1 - Pearson correlation
    braycurtis    sum(|a - b|) / sum(a + b)
    jaccard       1 - |A and B| / |A or B|, on binarized (>0) values
    hamming       fraction of positions where a != b, after
                  binarization

Missing values
--------------
Missing cells are filled with 0 before the computation. This is the
correct interpretation for abundance matrices (an unobserved
species has zero abundance), and it also matches how ``braycurtis``
and ``jaccard`` are normally applied.

Size guard
----------
The output is a dense ``n x n`` matrix. The memory planner reserves its
quadratic workspace/output before execution. An optional ``max_positions``
adds a user-selected count limit; no fixed count cap is imposed by default.

Params:
    dim            : axis to compute distances along (required)
    metric         : metric name (default "euclidean")
    max_positions  : refuse if dim has more positions than this
                     (default None; governed by the memory budget)
    output         : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: distance_matrix
  inputs: [<input1>]
  params:
    dim: <string>
    metric: <string; enum=['euclidean', 'manhattan', 'cosine', 'correlation', 'braycurtis', 'jaccard', 'hamming']>
    max_positions: <integer / null>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/distance_matrix.md` and regenerate.
