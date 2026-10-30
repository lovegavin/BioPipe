# jonckheere_terpstra

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/jonckheere_terpstra.py`](../../../src/task/step/steps/jonckheere_terpstra.py)
- Tests: [`tests/test_extension30.py`](../../../tests/test_extension30.py), [`tests/test_r_oracles22.py`](../../../tests/test_r_oracles22.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_order` | 分组顺序 | array |  |  |  |  | basic |
| `alternative` | 备择假设 | string; enum=['two-sided', 'increasing', 'decreasing'] | two-sided |  |  |  | basic |
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
Rank-based test for a monotone trend across ordered groups.

    The p-value uses the normal approximation, matching
    ``DescTools::JonckheereTerpstraTest(..., exact=FALSE)``. Ties are
    preserved in the statistic but the normal variance does not include a
    tie correction (the same convention as the R implementation).

--- module documentation ---

Jonckheere-Terpstra test for an ordered alternative.
```

## Minimal YAML skeleton

```yaml
- name: jonckheere_terpstra
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    group_label: <string>
    group_order: <array>
    alternative: <string; enum=['two-sided', 'increasing', 'decreasing']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/jonckheere_terpstra.md` and regenerate.
