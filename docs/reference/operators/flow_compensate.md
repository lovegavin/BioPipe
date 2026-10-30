# flow_compensate

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-readers`
- Source: [`src/task/step/steps/flow_compensate.py`](../../../src/task/step/steps/flow_compensate.py)
- Tests: [`tests/test_extension21.py`](../../../tests/test_extension21.py), [`tests/test_r_oracles13.py`](../../../tests/test_r_oracles13.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `event_dim` | Event Dim | string | event |  |  |  | basic |
| `channel_dim` | Channel Dim | string | channel |  |  |  | basic |
| `detector_dim` | Detector Dim | string | detector |  |  |  | basic |
| `fluorochrome_dim` | Fluorochrome Dim | string | fluorochrome |  |  |  | basic |
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
        "param": "event_dim",
        "default": "event"
      },
      {
        "param": "channel_dim",
        "default": "channel"
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
        "param": "detector_dim",
        "default": "detector"
      },
      {
        "param": "fluorochrome_dim",
        "default": "fluorochrome"
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
Fluorescence compensation for FCS event matrices, matching flowCore.
```

## Minimal YAML skeleton

```yaml
- name: flow_compensate
  inputs: [<input1>, <input2>]
  params:
    event_dim: <string>
    channel_dim: <string>
    detector_dim: <string>
    fluorochrome_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/flow_compensate.md` and regenerate.
