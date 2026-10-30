# mann_kendall

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/mann_kendall.py`](../../../src/task/step/steps/mann_kendall.py)
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `time_dim` | Time Dim | string | time |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
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
        "param": "time_dim",
        "default": "time"
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
Per-feature Mann-Kendall S, Kendall tau, z and two-sided p.

--- module documentation ---

Mann-Kendall monotonic trend test per feature.
```

## Minimal YAML skeleton

```yaml
- name: mann_kendall
  inputs: [<input1>]
  params:
    time_dim: <string>
    feature_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/mann_kendall.md` and regenerate.
