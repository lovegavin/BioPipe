# confusion_matrix

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/confusion_matrix.py`](../../../src/task/step/steps/confusion_matrix.py)
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `label_dim` | 标签维度 | string | label |  |  |  | basic |
| `true_label` | True Label | string |  |  |  | yes | basic |
| `pred_label` | Pred Label | string |  |  |  | yes | basic |
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
        "param": "label_dim",
        "default": "label"
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
Binary confusion matrix with actual rows and predicted columns.

--- module documentation ---

Confusion matrix for two binary label columns.
```

## Minimal YAML skeleton

```yaml
- name: confusion_matrix
  inputs: [<input1>]
  params:
    sample_dim: <string>
    label_dim: <string>
    true_label: <string>
    pred_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/confusion_matrix.md` and regenerate.
