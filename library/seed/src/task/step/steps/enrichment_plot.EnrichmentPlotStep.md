<!-- operon:generated -->
# enrichment_plot

## Purpose

> Horizontal bar plot of a GO enrichment result.
>
> Draws the top N terms from an ``enrich_go`` output as horizontal
> bars of ``-log10(Q)``, with bar color encoded by ``n_hit``. This is
> the standard summary figure for over-representation analysis.
>
> Layout
> ------
>     input   dims: [<term_dim>, "statistic"]
>     output  no Form; PNG written to the run figures directory
>
> The term axis and the statistic axis are detected from the input
> dims. ``Q_VALUE`` and ``n_hit`` must be present on the statistic
> axis, either from ``enrich_go`` or from an equivalent upstream.
>
> Params:
>     term_dim      : name of the term dimension (auto-detected)
>     statistic_dim : name of the statistic dimension (default "statistic")
>     q_column      : column holding the adjusted p-value (default "Q_VALUE")
>     size_column   : column driving bar color (default "n_hit")
>     top_n         : number of terms to plot, ranked by Q (default 20)
>     filename      : PNG filename inside the figures directory
>     title         : plot title
>
> Horizontal bar plot of enrichment results.

## Inputs and outputs

Kind: `operator`. Operator ID: `enrichment_plot`.
Input count: `1`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Runs in the shared Operon interpreter.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/enrichment_plot.py` (`EnrichmentPlotStep`).
