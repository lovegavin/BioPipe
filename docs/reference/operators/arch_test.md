# arch_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/arch_test.py`](../../../src/task/step/steps/arch_test.py)
- Tests: [`tests/test_extension21.py`](../../../tests/test_extension21.py), [`tests/test_r_oracles13.py`](../../../tests/test_r_oracles13.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `time_dim` | Time Dim | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `lags` | Lags | integer | 5 | 1 |  |  | basic |
| `demean` | Demean | boolean | False |  |  |  | basic |
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
ARCH Lagrange-multiplier test for conditional heteroskedasticity.
```

## Minimal YAML skeleton

```yaml
- name: arch_test
  inputs: [<input1>]
  params:
    time_dim: <string>
    feature_dim: <string>
    value_label: <string>
    lags: <integer>
    demean: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/arch_test.md` and regenerate.
