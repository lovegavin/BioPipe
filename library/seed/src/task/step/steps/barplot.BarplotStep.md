<!-- operon:generated -->
# Composition barplot

## Purpose

> Stacked bar plot of a matrix along one axis.
>
> Input is a 2D form. One axis is the "composition" axis (features
> that will be stacked) and the other is the "sample" axis (bars).
> For each sample, one bar is drawn, and the features are stacked in
> their order along the composition axis.
>
> This is the standard visualization for compositional data:
> relative abundance of taxa per sample, cell-type fractions per
> sample, isoform fractions, etc.
>
> Layout
> ------
>     input  dims: [<composition_dim>, <sample_dim>]  (any orientation)
>     output      : a barplot image
>
> Feature selection
> -----------------
> The operator can show only the top N most abundant features. The
> remaining features are summed into a single "Other" category.
>
> Normalization
> -------------
> ``normalize=True`` (default) divides each sample by its total, so
> each bar sums to 1. This is the correct default for compositional
> data. Set to False to plot raw values.
>
> Params:
>     dim          : composition dim (required)
>     sample_dim   : sample dim (required)
>     top_n        : show only the top N most abundant features
>                    (default 20; use 0 or None to show all)
>     other_label  : label for the aggregated remainder
>                    (default "Other")
>     normalize    : divide each sample by its total (default True)
>     filename     : output file name (required)
>     title        : optional plot title
>     xlabel       : optional x label (default: sample_dim)
>     ylabel       : optional y label (default: "Fraction" or "Value")
>     cmap         : matplotlib colormap (default "tab20")
>     figsize      : [width, height] in inches (default auto)
>     legend       : show a legend (default True)
>     legend_ncol  : number of columns in the legend (default 3)
>     rotate_labels: rotate x tick labels 90 degrees (default True)
>
> Stacked bar plot of a matrix along one axis.

## Inputs and outputs

Kind: `operator`. Operator ID: `barplot`.
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

Implementation: `src/task/step/steps/barplot.py` (`BarplotStep`).
