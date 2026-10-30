# flow_transform

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-readers`
- Source: [`src/task/step/steps/flow_transform.py`](../../../src/task/step/steps/flow_transform.py)
- Tests: [`tests/test_extension19.py`](../../../tests/test_extension19.py), [`tests/test_r_oracles11.py`](../../../tests/test_r_oracles11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `event_dim` | Event Dim | string | event |  |  |  | basic |
| `channel_dim` | Channel Dim | string | channel |  |  |  | basic |
| `channels` | Channels | array |  |  |  |  | basic |
| `a` | A | number | 1.0 |  |  |  | basic |
| `b` | B | number | 1.0 |  |  |  | basic |
| `c` | C | number | 0.0 |  |  |  | basic |
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
  "mode": "transform",
  "representation": "flow_arcsinh"
}
```

## Processing rules (source docstring)

```text
Arcsinh transform for FCS event matrices, matching flowCore.
```

## Minimal YAML skeleton

```yaml
- name: flow_transform
  inputs: [<input1>]
  params:
    event_dim: <string>
    channel_dim: <string>
    channels: <array>
    a: <number>
    b: <number>
    c: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/flow_transform.md` and regenerate.
