# moses_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/moses_test.py`](../../../src/task/step/steps/moses_test.py)
- Tests: [`tests/test_extension35.py`](../../../tests/test_extension35.py), [`tests/test_r_oracles27.py`](../../../tests/test_r_oracles27.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_a` | 第一组 | string |  |  |  | yes | basic |
| `group_b` | 第二组 | string |  |  |  | yes | basic |
| `extreme` | 每侧截尾个数 | integer |  | 0 |  |  | basic |
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
Moses two-sample test for extreme reactions.

--- module documentation ---

Moses test of extreme reactions.
```

## Minimal YAML skeleton

```yaml
- name: moses_test
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    group_label: <string>
    group_a: <string>
    group_b: <string>
    extreme: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/moses_test.md` and regenerate.
