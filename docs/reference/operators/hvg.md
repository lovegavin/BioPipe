# hvg

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/hvg.py`](../../../src/task/step/steps/hvg.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | gene |  |  |  | basic |
| `n_top` | N Top | integer | 2000 | 1 |  |  | basic |
| `min_mean` | Min Mean | number | 0.0 | 0 |  |  | basic |
| `max_mean` | Max Mean | number | 1000000000000.0 | 0 |  |  | basic |
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
        "default": "gene"
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
    "info_open": false,
    "axis_info_open": false,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    }
  }
}
```

## Processing rules (source docstring)

```text
Highly variable gene ranking by mean/variance dispersion.
```

## Minimal YAML skeleton

```yaml
- name: hvg
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    n_top: <integer>
    min_mean: <number>
    max_mean: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/hvg.md` and regenerate.
