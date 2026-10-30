# peptide_qvalue

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/peptide_qvalue.py`](../../../src/task/step/steps/peptide_qvalue.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `psm_dim` | Psm Dim | string | psm |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `score_label` | Score Label | string |  |  |  | yes | basic |
| `decoy_label` | Decoy Label | string |  |  |  | yes | basic |
| `decoy_values` | Decoy Values | array | [1] |  |  |  | basic |
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
        "param": "psm_dim",
        "default": "psm"
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
Target-decoy q-values for peptide-spectrum matches.
```

## Minimal YAML skeleton

```yaml
- name: peptide_qvalue
  inputs: [<input1>]
  params:
    psm_dim: <string>
    feature_dim: <string>
    score_label: <string>
    decoy_label: <string>
    decoy_values: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/peptide_qvalue.md` and regenerate.
