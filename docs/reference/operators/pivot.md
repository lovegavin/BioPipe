# pivot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/pivot.py`](../../../src/task/step/steps/pivot.py)
- Tests: [`tasks/go_enrichment_route_demo/test_gene_list_to_hits.py`](../../../tasks/go_enrichment_route_demo/test_gene_list_to_hits.py), [`tasks/pivot_demo/test_pivot.py`](../../../tasks/pivot_demo/test_pivot.py), [`tasks/verify_go_enrichment.py`](../../../tasks/verify_go_enrichment.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/enrich_go_demo/task.yaml`](../../../tasks/enrich_go_demo/task.yaml), [`tasks/enrichment_plot_demo/task.yaml`](../../../tasks/enrichment_plot_demo/task.yaml), [`tasks/go_enrichment_demo/task.yaml`](../../../tasks/go_enrichment_demo/task.yaml), [`tasks/go_enrichment_route_demo/task.yaml`](../../../tasks/go_enrichment_route_demo/task.yaml), [`tasks/pivot_demo/task.yaml`](../../../tasks/pivot_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `index_label` | Index column | string |  |  |  | yes | basic |
| `columns_label` | Columns column | string |  |  |  | yes | basic |
| `values_label` | Values column | string |  |  |  |  | basic |
| `index_name` | Row axis name | string |  |  |  |  | advanced |
| `columns_name` | Column axis name | string |  |  |  |  | advanced |
| `agg` | Aggregation | string; enum=['sum', 'first', 'max', 'min', 'count'] | sum |  |  |  | advanced |
| `output` | Output key | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
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
Pivot a long 2D table into a wide matrix by two categorical columns.

--- module documentation ---

Turn a long table into a wide matrix by two categorical columns.

The input is a 2D form whose ``field_dim`` holds a set of named
columns. Two of those columns are chosen: one becomes the row axis
of the output, the other becomes the column axis. A third column may
supply the cell value; without it, every observed pair contributes 1.

This is the standard way to build a gene x GO-term membership matrix
from a GAF file, a sample x feature matrix from a long CSV, or any
pair-count table that downstream matrix operators can consume.

Layout
------
    input   dims: [pair, field]
    output  dims: [<index_name>, <columns_name>]

Duplicate (index, column) pairs are combined by ``agg``.

A hard cell-count cap protects the runtime from accidentally
materialising a huge dense matrix. When the cap is exceeded, filter
the input to a smaller subset before pivoting.

Params:
    index_label   : column label on the input field dim, becomes the
                    row axis (required)
    columns_label : column label on the input field dim, becomes the
                    column axis (required)
    values_label  : column label supplying cell values; without it
                    every observed pair contributes 1
    index_name    : name of the output row dim (default: index_label)
    columns_name  : name of the output column dim (default: columns_label)
    agg           : sum | first | max | min | count (default sum)
    output        : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: pivot
  inputs: [<input1>]
  params:
    index_label: <string>
    columns_label: <string>
    values_label: <string>
    index_name: <string>
    columns_name: <string>
    agg: <string; enum=['sum', 'first', 'max', 'min', 'count']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/pivot.md` and regenerate.
