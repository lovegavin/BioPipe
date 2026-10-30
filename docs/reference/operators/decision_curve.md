# decision_curve

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/decision_curve.py`](../../../src/task/step/steps/decision_curve.py)
- Tests: [`tests/test_extension14.py`](../../../tests/test_extension14.py), [`tests/test_r_oracles6.py`](../../../tests/test_r_oracles6.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `outcome_label` | Outcome Label | string |  |  |  | yes | basic |
| `risk_label` | Risk Label | string |  |  |  | yes | basic |
| `positive_label` | Positive Label | string |  |  |  |  | basic |
| `thresholds` | Thresholds | array |  |  |  |  | basic |
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
Net benefit across risk thresholds (decision-curve analysis).

--- module documentation ---

Decision-curve analysis for a binary outcome and predicted risk.
```

## Minimal YAML skeleton

```yaml
- name: decision_curve
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    outcome_label: <string>
    risk_label: <string>
    positive_label: <string>
    thresholds: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/decision_curve.md` and regenerate.
