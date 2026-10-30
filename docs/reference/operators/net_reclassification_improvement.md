# net_reclassification_improvement

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/net_reclassification_improvement.py`](../../../src/task/step/steps/net_reclassification_improvement.py)
- Tests: [`tests/test_extension17.py`](../../../tests/test_extension17.py), [`tests/test_r_oracles9.py`](../../../tests/test_r_oracles9.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `outcome_label` | Outcome Label | string |  |  |  | yes | basic |
| `old_risk_label` | Old Risk Label | string |  |  |  | yes | basic |
| `new_risk_label` | New Risk Label | string |  |  |  | yes | basic |
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
Continuous net reclassification improvement for two risk predictions.
```

## Minimal YAML skeleton

```yaml
- name: net_reclassification_improvement
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    outcome_label: <string>
    old_risk_label: <string>
    new_risk_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/net_reclassification_improvement.md` and regenerate.
