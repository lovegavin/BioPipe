# roc_comparison

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/roc_comparison.py`](../../../src/task/step/steps/roc_comparison.py)
- Tests: [`tests/test_extension27.py`](../../../tests/test_extension27.py), [`tests/test_r_oracles19.py`](../../../tests/test_r_oracles19.py)
- Demo tasks: none found
- Inputs arity: `3`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `label_dim` | 标签维度 | string | label |  |  |  | basic |
| `score_dim` | Score Dim | string | score |  |  |  | basic |
| `target_label` | 目标字段 | string |  |  |  | yes | basic |
| `score_a` | Score A | string |  |  |  | yes | basic |
| `score_b` | Score B | string |  |  |  | yes | basic |
| `positive_label` | Positive Label | string |  |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 | 0.5 | 0.999 |  | basic |
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
        "param": "score_dim",
        "default": "score"
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
        "param": "score_dim",
        "default": "score"
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
Compare two AUCs measured on the same samples (DeLong).

--- module documentation ---

Paired DeLong test for two correlated ROC curves.
```

## Minimal YAML skeleton

```yaml
- name: roc_comparison
  inputs: [<input1>, <input2>, <input3>]
  params:
    sample_dim: <string>
    label_dim: <string>
    score_dim: <string>
    target_label: <string>
    score_a: <string>
    score_b: <string>
    positive_label: <string>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/roc_comparison.md` and regenerate.
