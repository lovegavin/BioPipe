# cochran_armitage

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cochran_armitage.py`](../../../src/task/step/steps/cochran_armitage.py)
- Tests: [`tests/test_extension12.py`](../../../tests/test_extension12.py), [`tests/test_r_oracles4.py`](../../../tests/test_r_oracles4.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `group_dim` | 分组维度 | string | group |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `cases_column` | Cases Column | string | cases |  |  |  | basic |
| `total_column` | Total Column | string | total |  |  |  | basic |
| `group_scores` | Group Scores | array |  |  |  |  | basic |
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
        "param": "group_dim",
        "default": "group"
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
Cochran-Armitage trend test for ordered groups.
```

## Minimal YAML skeleton

```yaml
- name: cochran_armitage
  inputs: [<input1>]
  params:
    group_dim: <string>
    feature_dim: <string>
    cases_column: <string>
    total_column: <string>
    group_scores: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cochran_armitage.md` and regenerate.
