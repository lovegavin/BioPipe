# combat

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/combat.py`](../../../src/task/step/steps/combat.py)
- Tests: [`tests/test_extension2_operators.py`](../../../tests/test_extension2_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `batch_label` | Batch Label | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['combat', 'mean_center'] | combat |  |  |  | basic |
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
        "param": "feature_dim",
        "default": "feature"
      },
      {
        "param": "sample_dim",
        "default": "sample"
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
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "batch_label",
        "default": null
      }
    ]
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
Batch correction with ComBat or per-batch mean centering.

ComBat is the empirical-Bayes location/scale correction from Johnson et
al. (2007), exposed through Scanpy's implementation. ``mean_center`` is
the simpler location-only baseline: subtract each batch's feature mean
and add the overall feature mean.

The metadata table supplies one batch label per expression sample. All
expression samples must be present in the metadata; extra metadata rows
are ignored. Non-finite expression values are rejected rather than
silently corrected.
```

## Minimal YAML skeleton

```yaml
- name: combat
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    batch_label: <string>
    method: <string; enum=['combat', 'mean_center']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/combat.md` and regenerate.
