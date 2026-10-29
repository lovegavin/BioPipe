# bonferroni

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/bonferroni.py`](../../../src/task/step/steps/bonferroni.py)
- Tests: [`tests/test_extension4.py`](../../../tests/test_extension4.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `statistic_dim` | Statistic Dim | string | statistic |  |  |  | basic |
| `value_dim` | Value Dim | string | pvalue |  |  |  | basic |
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
        "param": "feature_dim",
        "default": "feature"
      },
      {
        "param": "statistic",
        "default": "statistic"
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
Bonferroni multiple-testing correction.

Reads a feature x statistic table with one p-value column and writes
a feature x statistic table containing only qvalues. Bonferroni qvalues
are min(p * m, 1), where m is the number of finite p-values.
```

## Minimal YAML skeleton

```yaml
- name: bonferroni
  inputs: [<input1>]
  params:
    feature_dim: <string>
    statistic_dim: <string>
    value_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/bonferroni.md` and regenerate.
