# bai_perron

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/bai_perron.py`](../../../src/task/step/steps/bai_perron.py)
- Tests: [`tests/test_extension81.py`](../../../tests/test_extension81.py), [`tests/test_r_oracles71.py`](../../../tests/test_r_oracles71.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | Response Label | string |  |  |  | yes | basic |
| `predictors` | Predictors | array |  |  |  | yes | basic |
| `n_breaks` | N Breaks | integer | 2 | 1 | 5 |  | basic |
| `min_segment` | Min Segment | number | 0.15 | 0.05 | 0.5 |  | basic |
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
Bai-Perron multiple structural-break regression.
```

## Minimal YAML skeleton

```yaml
- name: bai_perron
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    predictors: <array>
    n_breaks: <integer>
    min_segment: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/bai_perron.md` and regenerate.
