# cuzick_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cuzick_test.py`](../../../src/task/step/steps/cuzick_test.py)
- Tests: [`tests/test_extension42.py`](../../../tests/test_extension42.py), [`tests/test_r_oracles33.py`](../../../tests/test_r_oracles33.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `group_dim` | 分组维度 | string | sample |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_scores` | Group Scores | array |  |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two.sided', 'greater', 'less'] | two.sided |  |  |  | basic |
| `continuity` | Continuity | boolean | False |  |  |  | basic |
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
      },
      {
        "param": "group_dim",
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
Cuzick's rank-based trend test across ordered groups.

    Groups are ordered by their encoded group code (the order in which labels
    first appear in the metadata). ``group_scores`` can override the default
    ``1..k`` scores; it must follow that same group order.

--- module documentation ---

Cuzick rank trend test for ordered groups.
```

## Minimal YAML skeleton

```yaml
- name: cuzick_test
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    group_dim: <string>
    group_label: <string>
    group_scores: <array>
    alternative: <string; enum=['two.sided', 'greater', 'less']>
    continuity: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cuzick_test.md` and regenerate.
