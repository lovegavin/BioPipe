# ssgsea

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/ssgsea.py`](../../../src/task/step/steps/ssgsea.py)
- Tests: [`tests/test_extension2_operators.py`](../../../tests/test_extension2_operators.py), [`tests/test_r_oracles.py`](../../../tests/test_r_oracles.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `gene_set_dim` | Gene Set Dim | string | gene_set |  |  |  | basic |
| `alpha` | 显著性水平 | number | 0.25 | 0.0 |  |  | advanced |
| `min_size` | Min Size | integer | 1 | 1 |  |  | basic |
| `normalize` | 归一化 | boolean | True |  |  |  | basic |
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
        "param": "gene_dim",
        "default": "gene"
      },
      {
        "param": "gene_set_dim",
        "default": "gene_set"
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
Single-sample Gene Set Enrichment Analysis (ssGSEA).

This follows the rank-based statistic used by GSVA's ``ssgsea`` method:
for each sample, genes are ranked, a weighted rank-sum is compared with
the expected rank-sum outside the set, and scores are normalized by the
global range. It is a per-sample score, not the sample-level GSEA null.

The implementation is independent of GSVA. ``tests/test_r_oracles.py``
compares it with ``GSVA::gsva(ssgseaParam(...))`` when R/GSVA is present.
```

## Minimal YAML skeleton

```yaml
- name: ssgsea
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    gene_dim: <string>
    gene_set_dim: <string>
    alpha: <number>
    min_size: <integer>
    normalize: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/ssgsea.md` and regenerate.
