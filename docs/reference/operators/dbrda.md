# dbrda

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/dbrda.py`](../../../src/task/step/steps/dbrda.py)
- Tests: [`tests/test_extension76.py`](../../../tests/test_extension76.py), [`tests/test_r_oracles66.py`](../../../tests/test_r_oracles66.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `response_dim` | Response Dim | string | feature |  |  |  | basic |
| `predictor_dim` | Predictor Dim | string | predictor |  |  |  | basic |
| `distance` | Distance | string; enum=['bray', 'euclidean'] | bray |  |  |  | basic |
| `n_components` | 主成分数 | integer | 2 | 1 |  |  | basic |
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
        "param": "response_dim",
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
        "param": "predictor_dim",
        "default": "predictor"
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
Constrain a PCoA of a distance matrix by explanatory variables.

--- module documentation ---

Distance-based redundancy analysis (db-RDA).
```

## Minimal YAML skeleton

```yaml
- name: dbrda
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    response_dim: <string>
    predictor_dim: <string>
    distance: <string; enum=['bray', 'euclidean']>
    n_components: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/dbrda.md` and regenerate.
