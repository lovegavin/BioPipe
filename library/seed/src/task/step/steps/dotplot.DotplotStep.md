<!-- operon:generated -->
# Dot plot

## Purpose

> Dot plot of feature values grouped by a label column.
>
> Two inputs share a sample dim. The first carries per-feature values
> across samples; the second carries group labels. For each (group,
> feature) cell the operator computes two statistics:
>
>     value       mean (or median, or sum) of the feature within
>                 the group
>     proportion  fraction of samples in the group whose value passes
>                 the "expressed" rule (non-zero by default)
>
> The result is drawn as a grid: x = features, y = groups, dot color
> = value, dot size = proportion. This is the standard marker dot
> plot in single-cell analysis, but it works on any two-form dataset
> with a grouping column.
>
> The same two statistics are exported as a table so the numbers are
> auditable.
>
> Params:
>     feature_dim     : feature dim on the data form (required)
>     group_dim       : sample dim shared by both forms (required)
>     features        : list of feature labels to show (required)
>     group_label     : column on the metadata's other dim (required)
>     groups          : optional list of groups to show, in order
>     statistic       : "mean" | "median" | "sum" (default "mean")
>     proportion_mode : "nonzero" | "threshold" (default "nonzero")
>     threshold       : value used when proportion_mode="threshold"
>     filename        : output file name (required)
>     title           : optional plot title
>     xlabel          : optional x label (default: feature_dim)
>     ylabel          : optional y label (default: group_label)
>     cmap            : matplotlib colormap (default "viridis")
>     dot_scale       : max dot size in points^2 (default 200)
>
> Dot plot of features grouped by a label column.

## Inputs and outputs

Kind: `operator`. Operator ID: `dotplot`.
Input count: `2`.
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

Implementation: `src/task/step/steps/dotplot.py` (`DotplotStep`).
