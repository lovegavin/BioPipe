# limma_de

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/limma_de.py`](../../../src/task/step/steps/limma_de.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py), [`tests/test_r_oracles.py`](../../../tests/test_r_oracles.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | protein |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_a` | A 组 | string / number |  |  |  | yes | basic |
| `group_b` | B 组 | string / number |  |  |  | yes | basic |
| `prior_df` | Prior Df | integer |  | 0 |  |  | basic |
| `correction` | Correction | string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by'] | fdr |  |  |  | basic |
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
        "default": "protein"
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
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "group_label",
        "default": null
      }
    ]
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
Two-group linear-model differential analysis with empirical Bayes.

This is a limma-style workflow: per-feature group means and residual
variances, variance shrinkage using an empirical-Bayes prior, moderated
t statistics and BH correction. It is an independent Python
implementation; it is not a byte-for-byte wrapper around R limma.

The prior variance is estimated with the standard log-variance /
trigamma moment approximation used by limma's ``fitFDist``. A balanced
two-group design with ``prior_df: 0`` reduces to the ordinary pooled
t-test, which is covered by a hand-calculated test.

Output columns: logFC, mean_a, mean_b, t, P_VALUE, Q_VALUE,
df_residual, df_prior.
```

## Minimal YAML skeleton

```yaml
- name: limma_de
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    group_label: <string>
    group_a: <string / number>
    group_b: <string / number>
    prior_df: <integer>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/limma_de.md` and regenerate.
