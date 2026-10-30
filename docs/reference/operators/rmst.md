# rmst

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/rmst.py`](../../../src/task/step/steps/rmst.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `time_label` | 随访时间字段 | string |  |  |  | yes | basic |
| `event_label` | 事件字段 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  |  | basic |
| `tau` | Tau | number / null | None |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
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
Restricted mean survival time (RMST) from a clinical table.
```

## Minimal YAML skeleton

```yaml
- name: rmst
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    time_label: <string>
    event_label: <string>
    group_label: <string>
    tau: <number / null>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/rmst.md` and regenerate.
