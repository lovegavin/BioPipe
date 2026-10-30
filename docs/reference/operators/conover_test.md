# conover_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/conover_test.py`](../../../src/task/step/steps/conover_test.py)
- Tests: [`tests/test_extension41.py`](../../../tests/test_extension41.py), [`tests/test_r_oracles32.py`](../../../tests/test_r_oracles32.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `group_dim` | 分组维度 | string | sample |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['holm', 'bonferroni', 'BH', 'BY', 'fdr', 'none'] | holm |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two.sided', 'less', 'greater'] | two.sided |  |  |  | basic |
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
        "param": "sample_dim",
        "default": "sample"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  },
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
        "param": "group_dim",
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
All-pairwise Conover comparisons for every feature.

    Mean-rank differences are tested with the Conover variance correction
    after Kruskal-Wallis, matching ``DescTools::ConoverTest``.

--- module documentation ---

Conover post-hoc pairwise comparisons after Kruskal-Wallis.
```

## Minimal YAML skeleton

```yaml
- name: conover_test
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    group_dim: <string>
    group_label: <string>
    method: <string; enum=['holm', 'bonferroni', 'BH', 'BY', 'fdr', 'none']>
    alternative: <string; enum=['two.sided', 'less', 'greater']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/conover_test.md` and regenerate.
