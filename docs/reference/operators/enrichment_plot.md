# enrichment_plot

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/enrichment_plot.py`](../../../src/task/step/steps/enrichment_plot.py)
- Tests: [`tasks/enrichment_plot_demo/test_enrichment_plot.py`](../../../tasks/enrichment_plot_demo/test_enrichment_plot.py)
- Demo tasks: [`tasks/enrichment_plot_demo/task.yaml`](../../../tasks/enrichment_plot_demo/task.yaml), [`tasks/go_enrichment_demo/task.yaml`](../../../tasks/go_enrichment_demo/task.yaml), [`tasks/go_enrichment_route_demo/task.yaml`](../../../tasks/go_enrichment_route_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `term_dim` | Term dimension | string |  |  |  |  | basic |
| `statistic_dim` | Statistic dimension | string | statistic |  |  |  | basic |
| `q_column` | Q-value column | string | Q_VALUE |  |  |  | basic |
| `size_column` | Color column | string | n_hit |  |  |  | basic |
| `top_n` | Top N terms | integer | 20 | 1 |  |  | basic |
| `filename` | Output filename | string | enrichment.png |  |  |  | basic |
| `title` | Plot title | string |  |  |  |  | basic |

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
  "mode": "report"
}
```

## Processing rules (source docstring)

```text
Horizontal bar plot of enrichment results.

--- module documentation ---

Horizontal bar plot of a GO enrichment result.

Draws the top N terms from an ``enrich_go`` output as horizontal
bars of ``-log10(Q)``, with bar color encoded by ``n_hit``. This is
the standard summary figure for over-representation analysis.

Layout
------
    input   dims: [<term_dim>, "statistic"]
    output  no Form; PNG written to the run figures directory

The term axis and the statistic axis are detected from the input
dims. ``Q_VALUE`` and ``n_hit`` must be present on the statistic
axis, either from ``enrich_go`` or from an equivalent upstream.

Params:
    term_dim      : name of the term dimension (auto-detected)
    statistic_dim : name of the statistic dimension (default "statistic")
    q_column      : column holding the adjusted p-value (default "Q_VALUE")
    size_column   : column driving bar color (default "n_hit")
    top_n         : number of terms to plot, ranked by Q (default 20)
    filename      : PNG filename inside the figures directory
    title         : plot title
```

## Minimal YAML skeleton

```yaml
- name: enrichment_plot
  inputs: [<input1>]
  params:
    term_dim: <string>
    statistic_dim: <string>
    q_column: <string>
    size_column: <string>
    top_n: <integer>
    filename: <string>
    title: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/enrichment_plot.md` and regenerate.
