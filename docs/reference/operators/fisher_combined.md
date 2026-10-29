# fisher_combined

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/fisher_combined.py`](../../../src/task/step/steps/fisher_combined.py)
- Tests: [`tests/test_extension4.py`](../../../tests/test_extension4.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `statistic_dim` | Statistic Dim | string | statistic |  |  |  | basic |
| `pvalue_dims` | Pvalue Dims | array | [] |  |  |  | basic |
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
        "param": "statistic_dim",
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
Fisher's combined probability test per feature.

Combines two or more p-value columns per feature using
scipy.stats.combine_pvalues(method="fisher"). Input layout is
feature x statistic with p-value columns labelled pvalue, pvalue1,
pvalue2, ...; output is feature x statistic with chi2 and P.
```

## Minimal YAML skeleton

```yaml
- name: fisher_combined
  inputs: [<input1>]
  params:
    feature_dim: <string>
    statistic_dim: <string>
    pvalue_dims: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/fisher_combined.md` and regenerate.
