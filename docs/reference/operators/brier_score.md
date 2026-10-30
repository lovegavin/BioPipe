# brier_score

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/brier_score.py`](../../../src/task/step/steps/brier_score.py)
- Tests: [`tests/test_extension16.py`](../../../tests/test_extension16.py), [`tests/test_r_oracles8.py`](../../../tests/test_r_oracles8.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `time_label` | 随访时间字段 | string |  |  |  | yes | basic |
| `event_label` | 事件字段 | string |  |  |  | yes | basic |
| `risk_label` | Risk Label | string |  |  |  | yes | basic |
| `times` | Times | array |  |  |  | yes | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
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
Cox PH Brier score with inverse-probability-of-censoring weights.

--- module documentation ---

Cox-model IPCW Brier score at one or more times.
```

## Minimal YAML skeleton

```yaml
- name: brier_score
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    time_label: <string>
    event_label: <string>
    risk_label: <string>
    times: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/brier_score.md` and regenerate.
