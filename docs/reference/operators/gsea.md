# gsea

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/gsea.py`](../../../src/task/step/steps/gsea.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `stat_dim` | 统计维度 | string | statistic |  |  |  | advanced |
| `gene_set_dim` | Gene Set Dim | string | gene_set |  |  |  | basic |
| `rank_label` | Rank Label | string | log2FC |  |  |  | basic |
| `weight` | Weight | number | 1.0 | 0 |  |  | basic |
| `n_permutations` | 置换次数 | integer | 1000 | 10 |  |  | basic |
| `seed` | Seed | integer | 0 |  |  |  | basic |
| `min_set_size` | Min Set Size | integer | 5 | 1 |  |  | basic |
| `max_set_size` | Max Set Size | integer | 500 | 1 |  |  | basic |
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
Abstract step.

Subclasses declare:

* ``name`` — matched against the manifest's ``name`` field.
* ``inputs_arity`` — number of input forms, or ``"*"`` for any.
* ``outputs`` — context keys the step registers on exit.

And implement ``run``. They may also implement ``export`` to
return a JSON-serializable dict of the step's full results.

--- module documentation ---

Preranked Gene Set Enrichment Analysis (GSEA).

This is the classical weighted Kolmogorov-Smirnov enrichment score
(Subramanian et al. 2005), followed by gene-set permutation p-values
and BH correction. It is intentionally labelled *preranked*: it does
not reorder samples or estimate per-sample phenotypes.

Inputs
------
ranked : [gene, statistic] with a ranking column (default log2FC)
sets   : [gene, gene_set] binary membership

The gene-set permutation null is the standard choice for preranked
GSEA when sample-level expression is not available. The number of
permutations is explicit and seeded; results are reproducible.

This implementation is independent of fgsea/clusterProfiler. The test
suite compares the enrichment-score calculation and null behavior.
```

## Minimal YAML skeleton

```yaml
- name: gsea
  inputs: [<input1>, <input2>]
  params:
    gene_dim: <string>
    stat_dim: <string>
    gene_set_dim: <string>
    rank_label: <string>
    weight: <number>
    n_permutations: <integer>
    seed: <integer>
    min_set_size: <integer>
    max_set_size: <integer>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/gsea.md` and regenerate.
