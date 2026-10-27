# gene_list_to_hits

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/gene_list_to_hits.py`](../../../src/task/step/steps/gene_list_to_hits.py)
- Tests: [`tasks/go_enrichment_route_demo/test_gene_list_to_hits.py`](../../../tasks/go_enrichment_route_demo/test_gene_list_to_hits.py), [`tasks/verify_go_enrichment.py`](../../../tasks/verify_go_enrichment.py)
- Demo tasks: [`tasks/go_enrichment_route_demo/task.yaml`](../../../tasks/go_enrichment_route_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `genes` | 基因列表 | array |  |  |  | yes | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `term_dim` | Term Dim | string | go_term |  |  |  | basic |
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
Turn a gene list into a subset hits matrix over a universe.

--- module documentation ---

Build a hits matrix from a gene list and a universe matrix.

Input:
    universe : 2D Form [gene, term]. Only the labels on the gene
               axis are used.
    params   : ``genes`` = list of gene labels

Output:
    hits     : 2D Form [gene, term], containing only the rows of
               the universe whose gene is in ``genes``. Values are
               taken from ``universe > 0``.

The output is a valid hits Form for ``enrich_go``: gene axis is a
subset of the universe, term axis matches the universe. Sending the
full universe with zeroed-out non-hit rows would make
``enrich_go`` count every universe gene as a hit gene (it uses the
hits form's row count as ``n``), so the operator drops non-hit rows
instead.

Params:
    genes    : list of gene labels (required)
    gene_dim : gene axis (default "gene")
    term_dim : term axis (default "go_term")
    output   : context key (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: gene_list_to_hits
  inputs: [<input1>]
  params:
    genes: <array>
    gene_dim: <string>
    term_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/gene_list_to_hits.md` and regenerate.
