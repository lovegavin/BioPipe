# mantel_haenszel

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/mantel_haenszel.py`](../../../src/task/step/steps/mantel_haenszel.py)
- Tests: [`tests/test_extension12.py`](../../../tests/test_extension12.py), [`tests/test_r_oracles4.py`](../../../tests/test_r_oracles4.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `stratum_dim` | Stratum Dim | string | stratum |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `case_exposed` | Case Exposed | string | case_exposed |  |  |  | basic |
| `case_unexposed` | Case Unexposed | string | case_unexposed |  |  |  | basic |
| `control_exposed` | Control Exposed | string | control_exposed |  |  |  | basic |
| `control_unexposed` | Control Unexposed | string | control_unexposed |  |  |  | basic |
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
        "param": "stratum_dim",
        "default": "stratum"
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
Mantel-Haenszel stratified odds ratio and association test.
```

## Minimal YAML skeleton

```yaml
- name: mantel_haenszel
  inputs: [<input1>]
  params:
    stratum_dim: <string>
    feature_dim: <string>
    case_exposed: <string>
    case_unexposed: <string>
    control_exposed: <string>
    control_unexposed: <string>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/mantel_haenszel.md` and regenerate.
