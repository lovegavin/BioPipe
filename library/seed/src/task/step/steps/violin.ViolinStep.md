<!-- operon:generated -->
# Violin plot

## Purpose

> Violin plot of one value column split by groups.
>
> Two inputs share a sample dim. The first carries a per-sample value
> column; the second carries a group label column. For each group the
> operator draws a kernel density estimate of the values, optionally
> with an inner box, quartile markers, or points.
>
> Domain-agnostic. Any 2D data form + any 2D metadata form with a
> grouping column works.
>
> Params:
>     dim             : dim of the data form that holds the value
>                       column (default "feature")
>     value_label     : column label to plot (required)
>     group_dim       : sample dim shared by both forms (required)
>     group_label     : column label on the metadata's other dim
>                       (required)
>     groups          : optional list of group names to keep, in order
>     filename        : output file name (required)
>     title           : optional plot title
>     xlabel          : optional x label (default: group_label)
>     ylabel          : optional y label (default: value_label)
>     inner           : "box" | "quartile" | "point" | "none"
>                       (default "box")
>     show_points     : overlay individual points (default False)
>     point_size      : marker size for overlay (default 4)
>     point_alpha     : marker transparency (default 0.5)
>     rotate_labels   : rotate x tick labels 45 degrees (default False)
>
> Draw violin plots of a value column grouped by a label.

## Inputs and outputs

Kind: `operator`. Operator ID: `violin`.
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

Implementation: `src/task/step/steps/violin.py` (`ViolinStep`).
