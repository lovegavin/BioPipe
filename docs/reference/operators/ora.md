# ora

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/ora.py`](../../../src/task/step/steps/ora.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py), [`tests/test_r_oracles.py`](../../../tests/test_r_oracles.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `stat_dim` | 统计维度 | string | statistic |  |  |  | advanced |
| `gene_set_dim` | Gene Set Dim | string | gene_set |  |  |  | basic |
| `p_label` | P 值字段 | string | Q_VALUE |  |  | yes | basic |
| `lfc_label` | log2FC 字段 | string | log2FC |  |  | yes | basic |
| `p_threshold` | P 值阈值 | number | 0.05 | 0 | 1 |  | basic |
| `lfc_threshold` | log2FC 阈值 | number | 0.0 | 0 |  |  | basic |
| `direction` | Direction | string; enum=['up', 'down', 'both'] | both |  |  |  | basic |
| `correction` | Correction | string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by'] | fdr |  |  |  | basic |
| `min_set_size` | Min Set Size | integer | 1 | 1 |  |  | basic |
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
        "param": "gene_dim",
        "default": "gene"
      },
      {
        "param": "stat_dim",
        "default": "statistic"
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
Over-representation analysis (hypergeometric test) for gene sets.

Inputs
------
stats : 2D [gene, statistic] with columns such as log2FC and Q_VALUE.
sets  : 2D [gene, gene_set] binary membership (for example GmtReader).

The hit set is selected from ``stats`` by adjusted p-value and absolute
log fold change. The universe is every gene present in ``stats``; genes
in a set that are absent from the universe are ignored and counted in
the export.

This is the classical Fisher/hypergeometric ORA, not GSEA.
```

## Minimal YAML skeleton

```yaml
- name: ora
  inputs: [<input1>, <input2>]
  params:
    gene_dim: <string>
    stat_dim: <string>
    gene_set_dim: <string>
    p_label: <string>
    lfc_label: <string>
    p_threshold: <number>
    lfc_threshold: <number>
    direction: <string; enum=['up', 'down', 'both']>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    min_set_size: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/ora.md` and regenerate.
