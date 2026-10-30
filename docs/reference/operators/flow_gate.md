# flow_gate

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-readers`
- Source: [`src/task/step/steps/flow_gate.py`](../../../src/task/step/steps/flow_gate.py)
- Tests: [`tests/test_extension19.py`](../../../tests/test_extension19.py), [`tests/test_r_oracles11.py`](../../../tests/test_r_oracles11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `event_dim` | Event Dim | string | event |  |  |  | basic |
| `channel_dim` | Channel Dim | string | channel |  |  |  | basic |
| `x_channel` | X Channel | string |  |  |  | yes | basic |
| `y_channel` | Y Channel | string |  |  |  | yes | basic |
| `x_min` | X Min | number |  |  |  | yes | basic |
| `x_max` | X Max | number |  |  |  | yes | basic |
| `y_min` | Y Min | number |  |  |  | yes | basic |
| `y_max` | Y Max | number |  |  |  | yes | basic |
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
Rectangular gating for FCS event matrices.
```

## Minimal YAML skeleton

```yaml
- name: flow_gate
  inputs: [<input1>]
  params:
    event_dim: <string>
    channel_dim: <string>
    x_channel: <string>
    y_channel: <string>
    x_min: <number>
    x_max: <number>
    y_min: <number>
    y_max: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/flow_gate.md` and regenerate.
