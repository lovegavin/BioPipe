# homogeneity_completeness_v_measure

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/homogeneity_completeness_v_measure.py`](../../../src/task/step/steps/homogeneity_completeness_v_measure.py)
- Tests: [`tests/test_extension55.py`](../../../tests/test_extension55.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `label_dim` | 标签维度 | string | label |  |  |  | basic |
| `label_a` | Label A | string |  |  |  | yes | basic |
| `label_b` | Label B | string |  |  |  | yes | basic |
| `beta` | Beta | number | 1.0 |  |  |  | basic |
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
Three entropy-based agreement scores for two partitions.

--- module documentation ---

Homogeneity, completeness, and V-measure for two label columns.
```

## Minimal YAML skeleton

```yaml
- name: homogeneity_completeness_v_measure
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    label_dim: <string>
    label_a: <string>
    label_b: <string>
    beta: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/homogeneity_completeness_v_measure.md` and regenerate.
