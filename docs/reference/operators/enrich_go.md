# enrich_go

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/enrich_go.py`](../../../src/task/step/steps/enrich_go.py)
- Tests: [`tasks/enrich_go_demo/test_enrich_go.py`](../../../tasks/enrich_go_demo/test_enrich_go.py), [`tasks/go_enrichment_route_demo/test_gene_list_to_hits.py`](../../../tasks/go_enrichment_route_demo/test_gene_list_to_hits.py), [`tasks/verify_go_enrichment.py`](../../../tasks/verify_go_enrichment.py), [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/enrich_go_demo/task.yaml`](../../../tasks/enrich_go_demo/task.yaml), [`tasks/enrichment_plot_demo/task.yaml`](../../../tasks/enrichment_plot_demo/task.yaml), [`tasks/go_enrichment_demo/task.yaml`](../../../tasks/go_enrichment_demo/task.yaml), [`tasks/go_enrichment_route_demo/task.yaml`](../../../tasks/go_enrichment_route_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `gene_dim` | Gene dimension | string | gene |  |  |  | basic |
| `term_dim` | Term dimension | string | go_term |  |  |  | basic |
| `correction` | Multiple-testing correction | string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by'] | fdr |  |  |  | basic |
| `min_term_size` | Minimum term size | integer | 1 | 1 |  |  | basic |
| `output` | Output key | string |  |  |  |  | basic |

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
        "param": "term_dim",
        "default": "go_term"
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
        "param": "term_dim",
        "default": "go_term"
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
Hypergeometric enrichment of one term axis over two inputs.

--- module documentation ---

GO term enrichment by the hypergeometric test.

Given a hit set and a background universe, both expressed as binary
gene x term matrices, this step computes for every term:

    N          total genes in the universe
    n          total genes in the hit set
    K          genes annotated to the term in the universe
    k          genes annotated to the term in the hit set
    expected   n * K / N
    P          P(X >= k | hypergeometric(N, K, n))
    Q          P adjusted by the requested multiple-testing method

The output is a term x statistic matrix, one row per term retained.

Layout
------
    hits       dims: [gene_dim, term_dim]
    universe   dims: [gene_dim, term_dim]
    output     dims: [term_dim, "statistic"]

Both inputs must share the same term labels. The hit set's genes
must be a subset of the universe's genes; otherwise the caller must
restrict the universe first.

Params:
    gene_dim       : name of the gene dimension (default "gene")
    term_dim       : name of the term dimension (default "go_term")
    correction     : fdr | bonferroni | holm | hommel | fdr_by
                     (default "fdr")
    min_term_size  : drop terms with fewer than this many genes in
                     the universe (default 1)
    output         : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: enrich_go
  inputs: [<input1>, <input2>]
  params:
    gene_dim: <string>
    term_dim: <string>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    min_term_size: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/enrich_go.md` and regenerate.
